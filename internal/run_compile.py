import argparse
from datetime import timedelta
import os
import subprocess
import sys
import json
import csv
import logging
import multiprocessing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep, time

"""
# 예시 (modelzoo/json/*.json 구조)
python dx-modelzoo/internal/run_compile.py \
    --model_dir ./onnx_models_from_s3
    
# 연결된 script (modelzoo/json/*.json 구조)
./internal/download_dataset.sh --dataset_dir=./datasets
sudo ln -s /home/deepx/dx-modelzoo/datasets /mnt/datasets
./internal/download_onnx_json_from_s3.sh --model_dir=./onnx_models_from_s3
python ./internal/run_compile.py --model_dir ./onnx_models_from_s3
    
# 예시 (res/json/v7/*.json 구조)
python ./internal/run_compile.py \
    --dxnn_format_version v7 \
    --model_dir ./models_test
   
# 연결된 script:
dx-all-suite/internal/run_compile_app_models.sh --output_path=./models_test --venv-reuse --dev --skip-upload-dxnn
"""

RETRY_LIMIT = 0

def setup_logger(log_file):
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console.setFormatter(formatter)
    logging.getLogger().addHandler(console)
    
def get_default_max_workers():
    try:
        num_cpu = multiprocessing.cpu_count()
        # Typically, using half the number of logical CPU cores is a reasonable choice.
        default_max_workers = max(1, num_cpu // 2)
        
        return default_max_workers
    except NotImplementedError:
        return 4

def load_model_list_from_file(file_path):
    if not os.path.isfile(file_path):
        logging.error(f"File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r") as f:
        models = [line.strip().replace('\r', '') for line in f if line.strip()]
    logging.info(f"Loaded {os.path.basename(file_path)} with {len(models)} models.")
    return models


def get_model_list(model_dir):
    json_dir = os.path.join(model_dir, "json")
    if not os.path.isdir(json_dir):
        logging.error(f"Directory not found: {json_dir}")
        sys.exit(1)

    models = [Path(f).stem for f in Path(json_dir).glob("*.json")]
    for model in models:
        print(model)
    sys.exit(0)


def compile_model(model_dir, dxnn_format_version, model, force, current_count=None, total_count=None, core_list_str=None):
    model_dir_path = Path(model_dir)
    output_dir = model_dir_path / "dxnn"
    output_dir.mkdir(exist_ok=True)

    onnx_path = model_dir_path / "onnx" / f"{model}.onnx"
    json_path = model_dir_path / "json" / f"{model}.json"
   
    if dxnn_format_version:
        json_path = model_dir_path / "json" / dxnn_format_version / f"{model}.json"
    
    log_path = output_dir / "log" / f"{model}.log"
    dxnn_path = output_dir / f"{model}.dxnn"

    progress_str = f"[{current_count}/{total_count}] " if current_count is not None and total_count is not None else ""

    # Check if the file exists and handle overwrite based on --force flag
    if dxnn_path.exists():
        if force:
            logging.warning(f"{progress_str}WARNING: File '{dxnn_path}' already exists. Overwriting due to --force option.")
        else:
            logging.warning(f"{progress_str}WARNING: File '{dxnn_path}' already exists. Skipping compilation. Use --force to overwrite.")
            return {"model": model, "success": True, "attempt": 1, "log_file": str(log_path), "duration": 0.0}

    base_cmd = [
        "dxcom",
        "-m", str(onnx_path),
        "-c", str(json_path),
        "-o", str(output_dir)
    ]

    cmd_list = []
    if core_list_str:
        cmd_list.extend(["taskset", "-c", core_list_str])
    cmd_list.extend(base_cmd)

    last_duration = 0.0
    for attempt in range(RETRY_LIMIT + 1):
        logging.info(f"{progress_str}Attempt {attempt + 1}/{RETRY_LIMIT + 1} to compile model: {model}")
        logging.info(f"Executing command: {' '.join(cmd_list)}")
        start_time = time()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as log_file:
            try:
                process = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    bufsize=1
                )
                for line in process.stdout:
                    print(f"[{model}] {line}", end="")
                    log_file.write(line)
                return_code = process.wait()
            
            except Exception as e:
                duration = time() - start_time
                last_duration = duration
                logging.error(f"An unexpected error occurred during compilation of {model} on attempt {attempt + 1}: {e}")
                if attempt < RETRY_LIMIT:
                    sleep(1)

        duration = time() - start_time
        last_duration = duration

        if return_code == 0:
            logging.info(f"✅ Model {model} compiled successfully. 소요 시간: {duration:.4f}초")
            return {"model": model, "success": True, "attempt": attempt + 1, "log_file": str(log_path), "duration": duration}
        else:
            logging.warning(f"❌ Model {model} failed on attempt {attempt + 1} with exit code {return_code}. 소요 시간: {duration:.4f}초")
            if attempt < RETRY_LIMIT:
                sleep(1)

    return {"model": model, "success": False, "attempt": RETRY_LIMIT + 1, "error": f"Compilation failed after {RETRY_LIMIT + 1} attempts. See log: {log_path}", "duration": last_duration}


def compile_models_parallel(model_dir, dxnn_format_version, models, max_workers, force):
    os.makedirs(os.path.join(model_dir, "dxnn"), exist_ok=True)
    results = []
    total_count = len(models)
    
    logging.info(f"MAX WORKERS: {max_workers}")
    logging.info(f"Compiling {total_count} models...")

    total_cores = os.cpu_count()
    use_taskset = True
    if total_cores is None:
        use_taskset = False
        logging.warning("Could not determine number of CPU cores. 'taskset' will not be used.")
    elif max_workers > total_cores:
        use_taskset = False
        logging.warning(f"max_workers ({max_workers}) > total cores ({total_cores}). 'taskset' will not be used to avoid conflicts.")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        cores_per_worker = 0
        if use_taskset and max_workers > 0:
            cores_per_worker = total_cores // max_workers

        for idx, model in enumerate(models):
            core_list_str = None
            if use_taskset and max_workers > 0 and cores_per_worker > 0:
                # Assign tasks to workers in a round-robin fashion
                worker_idx = idx % max_workers
                start_core = worker_idx * cores_per_worker

                # The last worker gets all remaining cores to handle uneven division
                if worker_idx == max_workers - 1:
                    end_core = total_cores - 1
                else:
                    end_core = start_core + cores_per_worker - 1

                core_list_str = f"{start_core}-{end_core}"
            futures.append(
                executor.submit(compile_model, model_dir, dxnn_format_version, model, force, current_count=idx + 1, total_count=total_count, core_list_str=core_list_str)
            )

        for future in as_completed(futures):
            results.append(future.result())

    return results


def save_results_json(results, summary, output_path):
    output_data = {"summary": summary, "results": results}
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)


def save_results_csv(results, summary, output_path):
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "success", "attempt", "duration", "log_file", "error"])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "model": r["model"],
                "success": r["success"],
                "attempt": r["attempt"],
                "duration": f"{r.get('duration', 0.0):.4f}",
                "log_file": r.get("log_file", ""),
                "error": r.get("error", "")
            })
        # Add summary at the end
        writer.writerow({})  # empty row for separation
        writer.writerow({"model": "--- Summary ---"})
        writer.writerow({"model": "Total Models", "success": summary["total_models"]})
        writer.writerow({"model": "Success", "success": summary["success"]})
        writer.writerow({"model": "Failed", "success": summary["failed"]})
        writer.writerow({"model": "Total Duration", "success": summary["total_duration_formatted"]})


def generate_html_dashboard(json_result_path, output_html_path):
    with open(json_result_path, "r") as f:
        data = json.load(f)

    summary = data.get("summary", {})
    results = data.get("results", [])
    success = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>DX Compiler Summary</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            .summary {{ margin-bottom: 20px; }}
            .success {{ color: green; }}
            .fail {{ color: red; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background-color: #f2f2f2; }}
            tr:hover {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h1>DX Compiler Results Summary</h1>
        <div class="summary">
            <p>Total models: {len(results)}</p>
            <p class="success">✅ Success: {len(success)}</p>
            <p class="fail">❌ Failed: {len(failed)}</p>
            <p>🕒 Total Duration: {summary.get('total_duration_formatted', 'N/A')}</p>
        </div>

        <h2>Success</h2>
        <table>
            <tr><th>Model</th><th>Attempts</th><th>Duration (s)</th></tr>
    """
    for r in success:
        duration_str = f"{r.get('duration', 0.0):.2f}"
        html += f"<tr><td>{r['model']}</td><td>{r['attempt']}</td><td>{duration_str}</td></tr>"

    html += """
        </table>

        <h2>Failed</h2>
        <table>
            <tr><th>Model</th><th>Attempts</th><th>Duration (s)</th><th>Error</th></tr>
    """
    for r in failed:
        error_snippet = r.get("error", "").split("\n")[0][:200]
        duration_str = f"{r.get('duration', 0.0):.2f}"
        html += f"<tr><td>{r['model']}</td><td>{r['attempt']}</td><td>{duration_str}</td><td><pre>{error_snippet}</pre></td></tr>"

    html += """
        </table>
    </body>
    </html>
    """
    # Ensure UTF-8 encoding for HTML file
    Path(output_html_path).write_text(html, encoding='utf-8')
    print(f"✅ HTML dashboard saved to: {output_html_path}")


def main():
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    parser = argparse.ArgumentParser(description="DXCOM Model Compiler with Logging & Retry")
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--dxnn_format_version")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--exclude_from")
    parser.add_argument("--include_from")
    parser.add_argument("--get_model_list", action="store_true")
    # cause of disable: Even when increasing the number of workers for parallel processing, the total compile time may actually increase.
    # parser.add_argument("--max_workers", type=int, default=get_default_max_workers())
    parser.add_argument("--max_workers", type=int, default=1)
    parser.add_argument("--log_file", default=f"run_compile_{timestamp}.log")
    parser.add_argument("--json_result", default=f"run_compile_results_{timestamp}.json")
    parser.add_argument("--csv_result", default=f"run_compile_results_{timestamp}.csv")
    parser.add_argument("--gen_html_report", action="store_true")
    args = parser.parse_args()

    args.model_dir = str(Path(args.model_dir).resolve())
    if args.exclude_from:
        args.exclude_from = str(Path(args.exclude_from).resolve())
    if args.include_from:
        args.include_from = str(Path(args.include_from).resolve())

    setup_logger(args.log_file)

    if args.get_model_list:
        get_model_list(args.model_dir)

    if not os.path.isdir(args.model_dir):
        logging.error(f"Invalid model directory: {args.model_dir}")
        sys.exit(1)

    dxnn_dir = os.path.join(args.model_dir, "dxnn")
    if os.path.exists(dxnn_dir) and args.force:
        import shutil
        logging.warning(f"Removing existing compiled directory: {dxnn_dir}")
        shutil.rmtree(dxnn_dir)

    # Filter model list
    if args.include_from:
        models = load_model_list_from_file(args.include_from)
    else:
        json_path = Path(args.model_dir, "json")
        
        if args.dxnn_format_version:
            json_path = Path(json_path, args.dxnn_format_version)
        
        all_models = [Path(f).stem for f in Path(args.model_dir, "json", json_path).glob("*.json")]
        if args.exclude_from:
            exclude = set(load_model_list_from_file(args.exclude_from))
            models = [m for m in all_models if m not in exclude]
        else:
            models = all_models

    start_compile_time = time()
    results = compile_models_parallel(args.model_dir, args.dxnn_format_version, models, args.max_workers, args.force)
    end_compile_time = time()

    duration = end_compile_time - start_compile_time
    formatted_duration = str(timedelta(seconds=int(duration)))

    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count
    failed = [r["model"] for r in results if not r["success"]]

    summary = {
        "total_models": len(results),
        "success": success_count,
        "failed": failed_count,
        "total_duration_seconds": duration,
        "total_duration_formatted": formatted_duration,
    }

    # Save results to files
    save_results_json(results, summary, args.json_result)
    logging.info(f"✅ JSON result saved to: {args.json_result}")
    save_results_csv(results, summary, args.csv_result)
    logging.info(f"✅ CSV result saved to: {args.csv_result}")

    if args.gen_html_report:
        html_output_path = Path(args.json_result).with_suffix(".html")
        generate_html_dashboard(args.json_result, str(html_output_path))

    logging.info(f"Compilation finished: {summary['success']} success, {summary['failed']} failed.")
    if failed:
        logging.error(f"Failed models: {failed}")


if __name__ == "__main__":
    start_time = time()
    main()
    end_time = time()
    duration = end_time - start_time
    formatted_duration = str(timedelta(seconds=int(duration)))
    logging.info(f"Total compile time: {formatted_duration}")
