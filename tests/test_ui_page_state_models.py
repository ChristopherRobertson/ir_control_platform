"""Page-state helper tests for the finished UI shell."""

from __future__ import annotations

import unittest

from ircp_ui_shell.page_state import PageStateKind, success_state, warning_state


class UiPageStateModelTests(unittest.TestCase):
    def test_success_state_helper_uses_success_kind_and_details(self) -> None:
        state = success_state(
            "Setup validated",
            "The current draft recipe passed the required checks.",
            details=("Ready for the focused Run workspace.",),
        )

        self.assertEqual(state.kind, PageStateKind.SUCCESS)
        self.assertEqual(state.title, "Setup validated")
        self.assertEqual(state.details, ("Ready for the focused Run workspace.",))

    def test_warning_state_helper_preserves_message(self) -> None:
        state = warning_state("Setup blocked", "Run remains disabled until setup is valid.")

        self.assertEqual(state.kind, PageStateKind.WARNING)
        self.assertEqual(state.message, "Run remains disabled until setup is valid.")


if __name__ == "__main__":
    unittest.main()
