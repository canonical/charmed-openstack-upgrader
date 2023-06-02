import unittest
from unittest.mock import MagicMock, call, patch

from cou.steps.backup import backup
from cou.steps.plan import apply_plan, dump_plan, generate_plan


class StepsPlanTestCase(unittest.TestCase):
    def test_generate_plan(self):
        args = MagicMock()
        plan = generate_plan(args)

        self.assertEqual(plan.description, "Top level plan")
        self.assertFalse(plan.parallel)
        self.assertIsNone(plan.function)
        self.assertEqual(len(plan.sub_steps), 1)

        sub_step = plan.sub_steps[0]
        self.assertEqual(sub_step.description, "backup mysql databases")
        self.assertFalse(sub_step.parallel)
        self.assertEqual(sub_step.function, backup)

    def test_apply_plan_continue(self):
        upgrade_plan = MagicMock()
        upgrade_plan.description = "Test Plan"
        upgrade_plan.run = MagicMock()

        with patch("cou.steps.plan.input") as mock_input, patch("cou.steps.plan.sys") as mock_sys:
            mock_input.return_value = "C"
            apply_plan(upgrade_plan)

            mock_input.assert_called_once_with("Test Plan[Continue/abort/skip]")
            upgrade_plan.run.assert_called_once()
            mock_sys.exit.assert_not_called()

    def test_apply_plan_abort(self):
        upgrade_plan = MagicMock()
        upgrade_plan.description = "Test Plan"

        with patch("cou.steps.plan.input") as mock_input, patch("cou.steps.plan.sys") as mock_sys:
            mock_input.return_value = "a"
            apply_plan(upgrade_plan)

            mock_input.assert_called_once_with("Test Plan[Continue/abort/skip]")
            upgrade_plan.function.assert_not_called()
            mock_sys.exit.assert_called_once_with(1)

    def test_apply_plan_skip(self):
        upgrade_plan = MagicMock()
        upgrade_plan.description = "Test Plan"
        sub_step = MagicMock()
        sub_step.description = sub_step
        upgrade_plan.sub_steps = [sub_step]

        with patch("cou.steps.plan.input") as mock_input, patch("cou.steps.plan.sys") as mock_sys:
            mock_input.return_value = "s"
            apply_plan(upgrade_plan)

            upgrade_plan.function.assert_not_called()
            mock_sys.exit.assert_not_called()

    def test_dump_plan(self):
        upgrade_plan = MagicMock()
        upgrade_plan.description = "Test Plan"
        sub_step = MagicMock()
        sub_step.description = "Sub Step"
        sub_step.sub_steps = []
        upgrade_plan.sub_steps = [sub_step]

        with patch("cou.steps.plan.logging.info") as mock_print:
            dump_plan(upgrade_plan)

            mock_print.assert_has_calls([call("Test Plan"), call("\tSub Step")])
            mock_print.call_count = 2
