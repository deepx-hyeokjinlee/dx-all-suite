#!/bin/bash

# USAGES:
# - public network : internal/run_compile_app_models.sh --dxnn_format_version=v8
# - private network: internal/run_compile_app_models.sh --dxnn_format_version=v8 --skip-upload-dxnn --skip-install-dx-compiler --skip-download-app-models
# Note: private network can not access to aws s3 to download app models and upload dxnn files, and also can not install dx-compiler by install.sh. So, it should use pre-downloaded app models. 

# 파일로 모델 목록 지정 (실패한 모델 목록 파일)
# internal/run_compile_app_models.sh --compile_list_file=./failed_models.txt --skip-install-dx-compiler --skip-download-app-models --skip-upload-dxnn

# CLI에서 직접 모델 지정
# internal/run_compile_app_models.sh --models=yolov7,resnet50 --skip-install-dx-compiler --skip-download-app-models --skip-upload-dxnn
    
# 두 방식 동시 사용 (합산 후 중복 제거)
# internal/run_compile_app_models.sh --compile_list_file=./failed.txt --models=new_model --skip-install-dx-compiler --skip-download-app-models --skip-upload-dxnn


SCRIPT_DIR=$(realpath "$(dirname "$0")")
DX_AS_PATH=$(realpath -s "${SCRIPT_DIR}/../")
COMPILER_PATH="${DX_AS_PATH}/dx-compiler"
RUNTIME_PATH="${DX_AS_PATH}/dx-runtime"

# Default VENV_PATH, can be overridden by --venv_path option
VENV_PATH_DEFAULT="${DX_AS_PATH}/internal/venv"
VENV_PATH="${VENV_PATH_DEFAULT}" # Initialize with default

# variables for venv options
VENV_PATH_ARG="" # Stores user-provided venv path
VENV_FORCE_REMOVE="n"
VENV_REUSE="n"

ENABLE_DEBUG_LOGS=0
ENABLE_DEV_MODE=0

# color env settings
source ${DX_AS_PATH}/scripts/color_env.sh
source ${DX_AS_PATH}/scripts/common_util.sh

WORKSPACE_PATH="${DX_AS_PATH}/internal/workspace"
OUTPUT_DIR="${WORKSPACE_PATH}/app_models"
AWS_CONFIG_FILE_PATH="${DX_AS_PATH}/internal/config/aws_config.properties"
DX_COM_CMD=dxcom
USE_FORCE=0
DXNN_FORMAT_VERSION="v8"
SKIP_UPLOAD_DXNN=0
SKIP_INSTALL_DX_COMPILER=0
SKIP_DOWNLOAD_APP_MODELS=0
COMPILE_LIST_FILE=""
COMPILE_MODELS=""

# Function to display help message
show_help() {
    print_colored "Usage: $(basename "$0") [--help ]" "YELLOW"
    print_colored "Options:" "GREEN"
    print_colored "  [--dxnn_format_version=<version>]  : Specify .dxnn format version (default: ${DXNN_FORMAT_VERSION})" "GREEN"
    print_colored "  [--output_path=<PATH>]             : Specify the path for the output directory (default: ${OUTPUT_DIR})" "GREEN"
    print_colored "  [--force]                          : Force overwrite if the file already exists" "GREEN"
    print_colored "  [--dev]                            : Use config/dev_config.properties instead of config/aws_config.properties" "GREEN"
    print_colored "  [--venv_path=<PATH>]               : Specify the path for the virtual environment (default: ${VENV_PATH_DEFAULT})" "GREEN"
    print_colored "  [--venv-force-remove]              : Force remove existing virtual environment at --venv_path before creation." "GREEN"
    print_colored "  [--venv-reuse]                     : Reuse existing virtual environment at --venv_path if it's valid, skipping creation." "GREEN"
    print_colored "  [--verbose]                        : Enable verbose (debug) logging." "GREEN"
    print_colored "  [--skip-upload-dxnn]               : Skip to upload compiled dxnn files to aws s3" "GREEN"
    print_colored "  [--skip-install-dx-compiler]       : Skip dx-compiler installation" "GREEN"
    print_colored "  [--skip-download-app-models]       : Skip downloading app models (onnx, json) files" "GREEN"
    print_colored "  [--compile_list_file=<PATH>]       : Compile only models listed in the specified file (one model name per line)" "GREEN"
    print_colored "  [--models=<LIST>]                  : Compile only the specified models (comma-separated, e.g. yolov7,resnet50)" "GREEN"
    print_colored "  [--help]                           : Show this help message" "GREEN"

    if [ "$1" == "error" ] && [[ ! -n "$2" ]]; then
        print_colored "Invalid or missing arguments." "ERROR"
        exit 1
    elif [ "$1" == "error" ] && [[ -n "$2" ]]; then
        print_colored "$2" "ERROR"
        exit 1
    elif [[ "$1" == "warn" ]] && [[ -n "$2" ]]; then
        print_colored "$2" "WARNING"
        return 0
    fi
    exit 0
}

install_dx_compiler() {
    if [ $SKIP_INSTALL_DX_COMPILER -eq 1 ]; then
        print_colored_v2 "WARNING" "skip to install dx-compiler"
        return
    fi
    
    print_colored_v2 "INFO" "--- dx-compiler is installing ---"
    DX_COM_INSTALL_CMD="${COMPILER_PATH}/install.sh --target=dx_com"
    echo "CMD : $DX_COM_INSTALL_CMD"
    $DX_COM_INSTALL_CMD || { print_colored "Install dx-compiler failed." "ERROR"; exit 1; }
    print_colored_v2 "INFO" "[OK] dx-compiler is installed."
}

download_app_models() {
    if [ $SKIP_DOWNLOAD_APP_MODELS -eq 1 ]; then
        print_colored_v2 "WARNING" "skip to download app models"
        return
    fi
    
    print_colored_v2 "INFO" "--- app models(onnx, json) files are downloading ---"
    
    PATTERN_ARGS="--include-pattern res/onnx/*.onnx --include-pattern res/json/${DXNN_FORMAT_VERSION}/*.json"
    
    # for testing
    # PATTERN_ARGS="--include-pattern res/onnx/YoloV7*.onnx --include-pattern res/json/${DXNN_FORMAT_VERSION}/YoloV7*.json"

    if [[ "$USE_FORCE" -eq 1 ]]; then
        print_colored_v2 "INFO" "Force option is enabled. Overwriting existing files."
        FORCE_ARGS="--force"
    fi

    DOWNLOAD_ONNX_CMD="dx-aws-s3 --config-file-path ${AWS_CONFIG_FILE_PATH} download --s3-path res --save-location ${OUTPUT_DIR} ${PATTERN_ARGS} ${FORCE_ARGS}" 
    
    echo "CMD : $DOWNLOAD_ONNX_CMD"
    $DOWNLOAD_ONNX_CMD || { print_colored "Download failed for app models(onnx, json)." "ERROR"; rm -rf ${OUTPUT_DIR}; exit 1; }
    print_colored_v2 "INFO" "[OK] app models(onnx, json) files are downloaded"
    tree ${OUTPUT_DIR}/onnx ${OUTPUT_DIR}/json
}

run_compile_app_models() {
    print_colored_v2 "INFO" "--- app models(onnx, json) are compiling ---"

    local calibration_dataset="${DX_AS_PATH}/getting-started/calibration_dataset"
    if [ ! -e "$calibration_dataset" ]; then
        ${DX_AS_PATH}/getting-started/compiler-2_setup_calibration_dataset.sh || { print_colored "Download failed for calibration dataset." "ERROR"; exit 1; }
    fi
    rm -rf ./calibration_dataset || true
    ln -s $calibration_dataset ./calibration_dataset || { print_colored "Create Symlink failed for calibration_dataset" "ERROR"; exit 1; }

    mkdir -p ./log

    MODEL_DIR_ARGS="--model_dir ${OUTPUT_DIR}"
    DXNN_FORMAT_VERSION_ARGS="--dxnn_format_version ${DXNN_FORMAT_VERSION}"
    RESULT_LOG_ARGS="--log_file ./log/run_compile_app_models.log --json_result ./log/run_compile_app_models_results.json --csv_result ./log/run_compile_app_models_results.csv"
    GEN_HTML_REPORT_ARGS="--gen_html_report"

    if [[ "$USE_FORCE" -eq 1 ]]; then
        print_colored_v2 "INFO" "Force option is enabled. Overwriting existing files."
        FORCE_ARGS="--force"
    fi

    FILTER_ARGS=""
    if [[ -n "$COMPILE_LIST_FILE" ]]; then
        print_colored_v2 "INFO" "Compile list file: ${COMPILE_LIST_FILE}"
        FILTER_ARGS+=" --include_from ${COMPILE_LIST_FILE}"
    fi
    if [[ -n "$COMPILE_MODELS" ]]; then
        print_colored_v2 "INFO" "Compile models: ${COMPILE_MODELS}"
        FILTER_ARGS+=" --models ${COMPILE_MODELS}"
    fi

    COMPILER_APP_MODEL_CMD="python ${DX_AS_PATH}/internal/run_compile.py ${MODEL_DIR_ARGS} ${DXNN_FORMAT_VERSION_ARGS} ${RESULT_LOG_ARGS} ${GEN_HTML_REPORT_ARGS} ${FORCE_ARGS} ${FILTER_ARGS}"
    echo "CMD : $COMPILER_APP_MODEL_CMD"
    $COMPILER_APP_MODEL_CMD || { print_colored "Compile failed for app models(onnx, json)." "ERROR"; exit 1; }
    rm -rf ./calibration_dataset || true

    print_colored_v2 "INFO" "[OK] app models(onnx, json) are compiled"
}

upload_dxnn_to_aws_s3() {
    if [ $SKIP_UPLOAD_DXNN -eq 1 ]; then
        print_colored_v2 "WARNING" "skip to upload dxnn to aws s3"
        return
    fi
    
    print_colored_v2 "INFO" "--- DXNN files uploading to s3://<your-bucket>/res/dxnn/${com_ver_dirname} ---"

    print_colored_v2 "INFO" "Get dx_com version to create s3 path"
    # 'DX-COM Version: 1.60.1'와 같은 출력에서 버전 문자열을 가져옴
    local com_version_str=$(${DX_COM_CMD} -v | grep 'DX-COM Version:')
    if [[ -z "$com_version_str" ]]; then
        print_colored_v2 "ERROR" "Failed to get dx_com version from '${DX_COM_CMD} -v'"
        exit 1
    fi

    # '1.60.1' 버전을 추출하고 '.'을 '_'로 변경하여 '1_60_1' 형식으로 만듬
    local com_ver_dirname=$(echo "$com_version_str" | sed -e 's/DX-COM Version: //' -e 's/\./_/g')
    print_colored_v2 "INFO" "DX-COM version for S3 path: ${com_ver_dirname}"

    local PATTERN_ARGS="--include-pattern ${OUTPUT_DIR}/dxnn/*.dxnn"
    local S3_UPLOAD_CMD="dx-aws-s3 --config-file-path ${AWS_CONFIG_FILE_PATH} upload --s3-path res/dxnn/${com_ver_dirname} --local-path ${OUTPUT_DIR}/dxnn ${PATTERN_ARGS}"

    print_colored_v2 "INFO" "Uploading dxnn files to S3..."
    echo "CMD: ${S3_UPLOAD_CMD}"
    ${S3_UPLOAD_CMD} || { print_colored_v2 "ERROR" "Upload dxnn files to S3 failed."; exit 1; }

    print_colored_v2 "INFO" "[OK] DXNN files uploaded to s3://<your-bucket>/res/dxnn/${com_ver_dirname}"
}

setup_venv() {
    print_colored_v2 "INFO" "--- setup python venv... ---"

    local VENV_CMD_ARGS="--venv_path=${VENV_PATH}"
    if [ "${VENV_FORCE_REMOVE}" = "y" ]; then
        VENV_CMD_ARGS+=" --venv-force-remove"
    fi
    if [ "${VENV_REUSE}" = "y" ]; then
        VENV_CMD_ARGS+=" --venv-reuse"
    fi

    # Pass the determined VENV_PATH and new options to install_python_and_venv.sh
    "${RUNTIME_PATH}/scripts/install_python_and_venv.sh" ${VENV_CMD_ARGS}
    if [ $? -ne 0 ]; then
        print_colored "Python and Virtual environment setup failed. Exiting." "ERROR"
        exit 1
    fi

    # Activate the venv for subsequent commands in this script
    . "${VENV_PATH}/bin/activate" || { print_colored "Failed to activate venv ${VENV_PATH}" "ERROR"; exit 1; }

    # for '--dev' mode
    if [ $ENABLE_DEV_MODE -eq 1 ]; then
        pip install -e ${SCRIPT_DIR}/.[test] || { print_colored "Install dx-aws-s3 failed." "ERROR"; exit 1; }
        print_colored_v2 "DEBUG" "ENABLE_DEV_MODE ON"

        DEV_CONFIG_FILE_PATH="${DX_AS_PATH}/internal/config/dev_config.properties"
        if [ -f ${DEV_CONFIG_FILE_PATH} ]; then
            source ${DEV_CONFIG_FILE_PATH}
            export DX_USERNAME
            export DX_PASSWORD
            export AWS_ACCESS_KEY
            export AWS_SECRET_KEY
            export BUCKET_NAME
            export REGION_NAME
            export CLOUDFRONT_DOMAIN
            print_colored_v2 "DEBUG" "dev config properties file $DEV_CONFIG_FILE_PATH is loadded."
        else
            print_colored_v2 "DEBUG" "dev config properties file $DEV_CONFIG_FILE_PATH is not found."
        fi
    else
        pip install ${SCRIPT_DIR}/. || { print_colored "Install dx-aws-s3 failed." "ERROR"; exit 1; }
    fi
    
    print_colored_v2 "INFO" "[OK] Completed to setup python venv to '${VENV_PATH}'"
}

main() {
    setup_venv
    install_dx_compiler
    download_app_models
    run_compile_app_models
    upload_dxnn_to_aws_s3
}

# parse args
for i in "$@"; do
    case "$1" in
        --dxnn_format_version=*)
            DXNN_FORMAT_VERSION="${1#*=}"
            ;;
        --output_path=*)
            OUTPUT_DIR="${1#*=}"
            ;;
        --force)
            USE_FORCE=1
            ;;
        --venv_path=*)
            VENV_PATH_ARG="${1#*=}"
            ;;
        --venv-force-remove)
            VENV_FORCE_REMOVE="y"
            ;;
        --venv-reuse)
            VENV_REUSE="y"
            ;;
        --verbose)
            ENABLE_DEBUG_LOGS=1
            ;;
        --dev)
            ENABLE_DEBUG_LOGS=1
            ENABLE_DEV_MODE=1
            ;;
        --skip-upload-dxnn)
            SKIP_UPLOAD_DXNN=1
            ;;
        --skip-install-dx-compiler)
            SKIP_INSTALL_DX_COMPILER=1
            ;;
        --skip-download-app-models)
            SKIP_DOWNLOAD_APP_MODELS=1
            ;;
        --compile_list_file=*)
            COMPILE_LIST_FILE="${1#*=}"
            ;;
        --models=*)
            COMPILE_MODELS="${1#*=}"
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            show_help "error" "Invalid option '$1'"
            ;;
    esac
    shift
done

# If user provided --venv_path, override the default VENV_PATH
if [ -n "${VENV_PATH_ARG}" ]; then
    VENV_PATH="${VENV_PATH_ARG}"
fi


main

exit 0
