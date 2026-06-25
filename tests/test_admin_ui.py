import unittest
from types import SimpleNamespace
from unittest.mock import patch

from main import (
    BTN_ADMIN,
    BTN_CATALOG,
    BTN_MATCHES,
    FilterSetup,
    _admin_keyboard,
    _ai_qa_demo_feedback_keyboard,
    _ai_qa_feedback_keyboard,
    _edit_filter_keyboard,
    _delete_filter_prompt,
    _edit_filter_prompt,
    _location_keyboard,
    _rent_keyboard,
    _rent_prompt,
    _rooms_keyboard,
    _settings_keyboard,
    _wbs_keyboard,
    handle_location_choice,
    handle_rent_choice,
    handle_rooms_choice,
    handle_wbs_choice,
    main_menu_keyboard,
)


class _FakeChat:
    id = 42


class _FakeMessage:
    chat = _FakeChat()
    message_id = 777

    def __init__(self) -> None:
        self.answered: list[tuple[str, object]] = []
        self.edited: list[tuple[str, object]] = []

    async def answer(self, text, reply_markup=None):
        self.answered.append((text, reply_markup))
        return self

    async def edit_text(self, text, reply_markup=None):
        self.edited.append((text, reply_markup))
        return self


class _FakeCallback:
    def __init__(self, data: str = "") -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=123)
        self.answered: list[tuple[str | None, bool | None]] = []

    async def answer(self, text=None, show_alert=None):
        self.answered.append((text, show_alert))


class _FakeState:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    async def update_data(self, **kwargs):
        self.data.update(kwargs)
        return self.data

    async def get_data(self):
        return dict(self.data)

    async def clear(self):
        self.data.clear()

    async def set_state(self, state):
        self.data["_state"] = state


class _FakeBot:
    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []

    async def delete_message(self, *, chat_id, message_id) -> None:
        self.deleted.append((chat_id, message_id))


class AdminUITests(unittest.TestCase):
    def _button_texts(self, keyboard) -> list[str]:
        return [
            button.text
            for row in keyboard.keyboard
            for button in row
        ]

    def test_admin_menu_contains_admin_button(self) -> None:
        keyboard = main_menu_keyboard(is_admin=True)

        self.assertIn(BTN_ADMIN, self._button_texts(keyboard))
        self.assertEqual(len(keyboard.keyboard), 3)

    def test_regular_menu_does_not_contain_admin_button(self) -> None:
        keyboard = main_menu_keyboard(is_admin=False)

        self.assertNotIn(BTN_ADMIN, self._button_texts(keyboard))
        self.assertEqual(
            self._button_texts(keyboard),
            [BTN_MATCHES, "⚙ Filter", BTN_CATALOG],
        )

    def _inline_button_texts(self, keyboard) -> list[str]:
        return [
            button.text
            for row in keyboard.inline_keyboard
            for button in row
        ]

    def test_settings_keyboard_collapses_admin_actions_into_admin_panel(self) -> None:
        configured_keyboard = _settings_keyboard(has_filter=True)
        empty_keyboard = _settings_keyboard(has_filter=False)

        self.assertNotIn("Admin panel", self._inline_button_texts(configured_keyboard))
        self.assertNotIn("Admin panel", self._inline_button_texts(empty_keyboard))
        self.assertEqual(
            self._inline_button_texts(configured_keyboard),
            ["Show matches", "Edit filter", "Reset filter", "🗑 Delete my data"],
        )

    def test_edit_filter_keyboard_reuses_field_edit_callbacks(self) -> None:
        keyboard = _edit_filter_keyboard()
        buttons = [
            button
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertEqual(
            [(button.text, button.callback_data) for button in buttons],
            [
                ("WBS", "settings:edit:wbs"),
                ("District", "settings:edit:location"),
                ("Rent", "settings:edit:rent"),
                ("Rooms", "settings:edit:rooms"),
                ("Back to filter", "settings:back"),
            ],
        )

    def test_admin_panel_contains_task_oriented_buttons(self) -> None:
        keyboard = _admin_keyboard()
        inline_texts = self._inline_button_texts(keyboard)

        self.assertEqual(
            inline_texts,
            [
                "Run QA demo",
                "Review flagged issues",
                "View QA metrics",
                "📊 Effectiveness dashboard",
                "Refresh catalog",
                "Run catalog QA",
            ],
        )

    def test_admin_panel_rows_stay_within_two_buttons(self) -> None:
        keyboard = _admin_keyboard()
        for row in keyboard.inline_keyboard:
            self.assertLessEqual(len(row), 2)

    def test_admin_panel_links_to_dashboard(self) -> None:
        keyboard = _admin_keyboard()
        dashboard = next(
            button
            for row in keyboard.inline_keyboard
            for button in row
            if button.text == "📊 Effectiveness dashboard"
        )
        # Without DASHBOARD_URL the button falls back to an explainer callback.
        self.assertEqual(dashboard.callback_data, "settings:dashboard")

    def test_rent_step_offers_presets_no_limit_and_cancel(self) -> None:
        keyboard = _rent_keyboard()
        texts = [
            button.text
            for row in keyboard.inline_keyboard
            for button in row
        ]
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertIn("No limit", texts)
        self.assertIn("filter:rent:NO_LIMIT", callbacks)
        self.assertIn("filter:rent:600", callbacks)
        self.assertIn("✖ Cancel", texts)
        self.assertIn("tap the button below", _rent_prompt())
        self.assertNotIn("send 0", _rent_prompt())

    def test_setup_step_keyboard_has_nav_row(self) -> None:
        # First step: cancel only, no back.
        wbs_nav = [b.text for b in _wbs_keyboard().inline_keyboard[-1]]
        self.assertEqual(wbs_nav, ["✖ Cancel"])

        # Later steps expose both back and cancel.
        loc_nav = [b.text for b in _location_keyboard(include_back=True).inline_keyboard[-1]]
        self.assertEqual(loc_nav, ["⬅ Back", "✖ Cancel"])

    def test_setup_keyboard_marks_current_selection(self) -> None:
        keyboard = _wbs_keyboard(selected="WBS 140")
        texts = [b.text for row in keyboard.inline_keyboard for b in row]
        self.assertIn("✓ WBS 140", texts)

    def test_filter_choice_keyboards_have_valid_callbacks(self) -> None:
        callback_data = [
            button.callback_data
            for keyboard in (_wbs_keyboard(), _location_keyboard(), _rent_keyboard(), _rooms_keyboard())
            for row in keyboard.inline_keyboard
            for button in row
        ]

        # 31 choice buttons (7 WBS + 13 districts + 5 rent + 6 rooms) plus one
        # Cancel button per keyboard (4) = 35 total.
        self.assertEqual(len(callback_data), 35)
        self.assertTrue(all(value for value in callback_data))
        self.assertTrue(all(len(value.encode("utf-8")) <= 64 for value in callback_data))
        self.assertTrue(all(value.startswith("filter:") for value in callback_data))

    def test_ai_qa_feedback_keyboard_has_triage_buttons(self) -> None:
        keyboard = _ai_qa_feedback_keyboard(123)
        inline_texts = [
            button.text
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertEqual(
            inline_texts,
            ["Parser error", "Parser correct", "Borderline / unsure"],
        )

    def test_ai_qa_demo_feedback_keyboard_has_same_triage_buttons(self) -> None:
        keyboard = _ai_qa_demo_feedback_keyboard()
        inline_texts = [
            button.text
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertEqual(
            inline_texts,
            ["Parser error", "Parser correct", "Borderline / unsure"],
        )


class FilterPromptLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_filter_prompt_is_edited_in_place(self) -> None:
        callback = _FakeCallback()
        state = _FakeState()
        keyboard = _rent_keyboard()

        await _edit_filter_prompt(callback, state, "Next question", keyboard)

        self.assertEqual(callback.message.edited, [("Next question", keyboard)])
        self.assertEqual(callback.message.answered, [])
        self.assertEqual(state.data["filter_prompt_chat_id"], 42)
        self.assertEqual(state.data["filter_prompt_message_id"], 777)

    async def test_remembered_filter_prompt_can_be_deleted(self) -> None:
        state = _FakeState()
        await state.update_data(filter_prompt_chat_id=42, filter_prompt_message_id=777)
        bot = _FakeBot()

        await _delete_filter_prompt(bot, state)

        self.assertEqual(bot.deleted, [(42, 777)])
        self.assertIsNone(state.data["filter_prompt_chat_id"])
        self.assertIsNone(state.data["filter_prompt_message_id"])

    async def test_filter_choice_buttons_advance_through_all_steps(self) -> None:
        state = _FakeState()

        wbs_callback = _FakeCallback("filter:wbs:WBS 160")
        await handle_wbs_choice(wbs_callback, state)
        self.assertEqual(state.data["wbs_type"], "WBS 160")
        self.assertEqual(state.data["_state"], FilterSetup.choosing_location)
        self.assertIn(
            "Which district should I search in?",
            wbs_callback.message.edited[-1][0],
        )

        location_callback = _FakeCallback("filter:location:Treptow-Köpenick")
        location_callback.message = wbs_callback.message
        await handle_location_choice(location_callback, state)
        self.assertEqual(state.data["location"], "Treptow-Köpenick")
        self.assertEqual(state.data["_state"], FilterSetup.choosing_rent)
        self.assertIn("maximum Kaltmiete", location_callback.message.edited[-1][0])

        rent_callback = _FakeCallback("filter:rent:NO_LIMIT")
        rent_callback.message = location_callback.message
        await handle_rent_choice(rent_callback, state)
        self.assertIsNone(state.data["max_rent"])
        self.assertEqual(state.data["_state"], FilterSetup.choosing_rooms)
        self.assertIn("How many rooms do you need?", rent_callback.message.edited[-1][0])

        rooms_callback = _FakeCallback("filter:rooms:3")
        rooms_callback.message = rent_callback.message
        with patch("main.save_fixed_preferences") as save_fixed_preferences:
            await handle_rooms_choice(rooms_callback, state)

        save_fixed_preferences.assert_called_once()
        self.assertEqual(state.data, {})
        self.assertIn("Filter saved.", rooms_callback.message.edited[-1][0])


if __name__ == "__main__":
    unittest.main()
