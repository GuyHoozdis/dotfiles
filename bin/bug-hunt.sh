#!/usr/bin/env bash
#
# $ pytest --no-print-logs ... \
#     pos_api/tests/controllers/test_modifiergroup.py::TestModifierGroupController::test_update_modifier_items_adds_removes_and_updates \
#     pos_api/tests/controllers/test_modifiergroup.py::TestModifierGroupController::test_rename_instructions_in_modifier_group \
#     pos_api/tests/controllers/test_modifiergroup.py::TestModifierGroupController::test_replace_item_in_modifier_group

set -eou pipefail

DEBBUGGER_CMDLINE_OPTIONS=""
[ ! -z ${TEST_DEBUG:-} ] \
  && STYLE=underline COLOR=cyan format-message "!!! Debug mode enabled !!!" \
  && DEBBUGGER_CMDLINE_OPTIONS="--pdb --pdbcls=ipdb.__main__:debugger_cls"


TEST_MODULE=pos_api/tests/controllers/test_modifiergroup.py
TEST_SUITE=TestModifierGroupController
TEST_CASES=(test_update_modifier_items_adds_removes_and_updates test_rename_instructions_in_modifier_group test_replace_item_in_modifier_group)

function run_scenarios() {
  local extra=${1-""}

  set -x
  pytest -v --no-cov --no-print-logs --showlocals --color=yes \
    $DEBBUGGER_CMDLINE_OPTIONS \
    ${TEST_MODULE}::${TEST_SUITE}::${TEST_CASES[0]} \
    ${TEST_MODULE}::${TEST_SUITE}::${TEST_CASES[1]} \
    ${TEST_MODULE}::${TEST_SUITE}::${TEST_CASES[2]}

  return $?
}


echo "Running test scenarios"
run_scenarios $@


