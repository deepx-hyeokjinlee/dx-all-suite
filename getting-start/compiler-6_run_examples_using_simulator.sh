#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
COMPILER_PATH=$(realpath -s "${SCRIPT_DIR}/../dx-compiler")
DX_SIMULATOR_PATH=$(realpath -s "${COMPILER_PATH}/dx_simulator")
DX_AS_PATH=$(realpath -s "${COMPILER_PATH}/..")

# color env settings
source ${DX_AS_PATH}/scripts/color_env.sh

echo -e "======== PATH INFO ========="
echo "DX_SIMULATOR_PATH($DX_SIMULATOR_PATH)"
echo "DX_AS_PATH($DX_AS_PATH)"
echo -e "============================"

pushd ${SCRIPT_DIR}

FORK_PATH="./forked_example"

# fork dx_simulator ${example_file_name} example code and input images
fork_examples() {
    local example_file_name=$1

    echo -e "=== fork dx_simulator examples to './forked_example' ${TAG_START} ==="
    
    
    CP_SOURCE_CMD="cp -dp ${DX_SIMULATOR_PATH}/examples/example_${example_file_name}.py ${FORK_PATH}/."
    echo "$CP_SOURCE_CMD"
    $CP_SOURCE_CMD
    if [ $? -ne 0 ]; then
        echo -e "${TAG_ERROR} Fork examples source failed!"
        exit 1
    fi

    CP_INPUT_IMAGE_CMD="cp -dpR ${DX_SIMULATOR_PATH}/examples/images ${FORK_PATH}/."
    echo "$CP_INPUT_IMAGE_CMD"
    $CP_INPUT_IMAGE_CMD
    if [ $? -ne 0 ]; then
        echo -e "${TAG_ERROR} Fork examples input image failed!"
        exit 1
    fi
    
    echo -e "=== fork dx_simulator examples to './forked_example' ${TAG_DONE} ==="
}

hijack_example_path() {
    local example_file_name=$1
    local input_img_name=$2
    local source_model_name=$3
    local target_model_name=$4

    echo -e "=== hijack example path ${TAG_START} ==="
    TARGET_FILE=${FORK_PATH}/example_${example_file_name}.py
    ORIGIN_FILE=${FORK_PATH}/example_${example_file_name}.py.bak

    cp ${TARGET_FILE} ${ORIGIN_FILE}

    HIJACK_CMD="sed -i \
    -e 's|examples/compiled_results/${source_model_name}.dxnn|dxnn/${target_model_name}.dxnn|g' \
    -e 's|examples/images/${input_img_name}.jpg|${FORK_PATH}/images/${input_img_name}.jpg|g' \
    -e 's|examples/${example_file_name}.jpg|${FORK_PATH}/result-${target_model_name}.jpg|g' \
    ${TARGET_FILE}"

    echo "$HIJACK_CMD"
    eval "$HIJACK_CMD"
    if [ $? -ne 0 ]; then
        echo -e "${TAG_ERROR} Hijack example path failed!"
        exit 1
    fi

    echo -e "=== show hijacking diff [BEGIN] ==="
    diff ${ORIGIN_FILE} ${TARGET_FILE}
    echo -e "=== show hijacking diff [END] ==="
    echo -e "=== hijack example path ${TAG_DONE} ==="
}

run_example_using_simulator() {
    local example_file_name=$1

    echo -e "=== run example using dx_simulator - model: ${model_name} ${TAG_START} ==="
    # activate python venv for dx_simulator
    ACTVATE_VENV_CMD="source ${DX_SIMULATOR_PATH}/venv-dx-simulator/bin/activate"
    echo "$ACTVATE_VENV_CMD"
    $ACTVATE_VENV_CMD
    if [ $? -ne 0 ]; then
        echo -e "${TAG_ERROR} Activate venv-dx-simulator failed!"
        echo -e "${TAG_INFO} (Hint) Please install the required dependency packages for 'dx_simulator' using the command below."
        echo -e "(Command) ${DX_SIMULATOR_PATH}/scripts/install.sh"
        exit 1
    fi

    # run hijakced python example source
    RUN_CMD="python ${FORK_PATH}/example_${example_file_name}.py"
    echo "$RUN_CMD"
    $RUN_CMD
    if [ $? -ne 0 ]; then
        echo -e "${TAG_ERROR} Run hijacked python example source(${FORK_PATH}/example_${example_file_name}.py) failed!"
        exit 1
    fi

    echo -e "=== run example using dx_simulator - model: ${model_name} ${TAG_DONE} ==="
}

main() {
    EXAMPLE_FILE_NAME_LIST=("yolov5s" "yolov5face" "classification")
    INPUT_IMG_NAME_LIST=("baseball" "baseball" "gold_fish")
    SOURCE_MODEL_NAME_NAME_LIST=("yolov5s" "yolov5face" "mobilenetv2")
    TARGET_MODEL_NAME_LIST=("YOLOV5S-1" "YOLOV5S_Face-1" "MobileNetV2-1")

    if [ -d "${FORK_PATH}" ]; then
        echo "forked example (${FORK_PATH}) already exists. It will be removed and recreated."
        rm -rf ${FORK_PATH}
    fi
    mkdir -p ${FORK_PATH}

    for i in "${!EXAMPLE_FILE_NAME_LIST[@]}"; do
        fork_examples ${EXAMPLE_FILE_NAME_LIST[$i]}
    done

    for i in "${!EXAMPLE_FILE_NAME_LIST[@]}"; do
        hijack_example_path ${EXAMPLE_FILE_NAME_LIST[$i]} ${INPUT_IMG_NAME_LIST[$i]} ${SOURCE_MODEL_NAME_NAME_LIST[$i]} ${TARGET_MODEL_NAME_LIST[$i]}
    done

    for i in "${!EXAMPLE_FILE_NAME_LIST[@]}"; do
        run_example_using_simulator ${EXAMPLE_FILE_NAME_LIST[$i]}
    done
}

main

popd

exit 0

