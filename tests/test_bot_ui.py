import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from main import (
    BTN_MATCHES,
    BTN_SETTINGS,
    FilterSetup,
    _ai_qa_feedback_keyboard,
    _delete_filter_prompt,
    _edit_filter_keyboard,
    _edit_filter_prompt,
    _filter_summary,
    _help_text,
    _location_keyboard,
    _no_filter_keyboard,
    _no_matches_keyboard,
    _public_bot_commands,
    _rent_keyboard,
    _rent_prompt,
    _rooms_keyboard,
    _settings_card,
    _settings_keyboard,
    _wbs_keyboard,
    handle_location_choice,
    handle_legacy_product_callback,
    handle_rent_choice,
    handle_rooms_choice,
    handle_wbs_choice,
    main_menu_keyboard,
    send_active_filtered_matches,
)
from flatfeed.schemas import UserPreferences


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


class BotUITests(unittest.TestCase):
    def test_public_command_menu_is_demo_only(self):
        commands = _public_bot_commands()

        self.assertEqual([item.command for item in commands], ["start", "help"])

    @staticmethod
    def _reply_button_texts(keyboard) -> list[str]:
        return [button.text for row in keyboard.keyboard for button in row]

    @staticmethod
    def _inline_button_texts(keyboard) -> list[str]:
        return [button.text for row in keyboard.inline_keyboard for button in row]

    def test_main_menu_contains_only_primary_product_actions(self) -> None:
        keyboard = main_menu_keyboard()

        self.assertEqual(
            self._reply_button_texts(keyboard),
            [BTN_MATCHES, BTN_SETTINGS],
        )
        self.assertEqual(len(keyboard.keyboard), 2)

    def test_empty_and_no_match_states_return_to_core_paths(self) -> None:
        self.assertEqual(
            self._inline_button_texts(_no_filter_keyboard()),
            ["Set up filter", "See the product flow"],
        )
        self.assertEqual(
            self._inline_button_texts(_no_matches_keyboard()),
            ["Edit filter", "See the product flow"],
        )

    def test_settings_keyboard_contains_only_filter_actions(self) -> None:
        configured_keyboard = _settings_keyboard(has_filter=True)
        empty_keyboard = _settings_keyboard(has_filter=False)

        self.assertEqual(
            self._inline_button_texts(configured_keyboard),
            ["Show matches", "Edit filter", "Reset filter", "🗑 Delete my data"],
        )
        self.assertEqual(
            self._inline_button_texts(empty_keyboard),
            ["Set up filter"],
        )

    def test_saved_filter_copy_matches_scheduler_state(self) -> None:
        preferences = UserPreferences(
            location=["Lichtenberg"],
            wbs_type="WBS 140",
            max_rent=600,
            rooms=2,
        )
        with patch("main.get_settings") as get_settings:
            get_settings.return_value = SimpleNamespace(bot_background_enabled=False)
            self.assertIn("matches on demand", _settings_card(preferences))
            self.assertNotIn("Notifications:</b> ON", _settings_card(preferences))
            self.assertIn("Tap Show matches", _filter_summary(preferences))

            get_settings.return_value = SimpleNamespace(bot_background_enabled=True)
            self.assertIn("Notifications:</b> ON", _settings_card(preferences))
            self.assertIn("send new matching listings", _filter_summary(preferences))

    def test_help_names_the_prototype_notification_boundary(self) -> None:
        text = _help_text()

        self.assertIn("does not monitor live housing sources", text)
        self.assertIn("notifications about real new listings", text)
        self.assertIn("/start — start or replay the demo", text)
        for retired_action in ("Show matches", "Set up my filter", "/filter", "/matches"):
            self.assertNotIn(retired_action, text)

    def test_edit_filter_keyboard_reuses_field_edit_callbacks(self) -> None:
        buttons = [
            button
            for row in _edit_filter_keyboard().inline_keyboard
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

    def test_rent_step_offers_presets_no_limit_and_cancel(self) -> None:
        keyboard = _rent_keyboard()
        texts = [button.text for row in keyboard.inline_keyboard for button in row]
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertIn("No limit", texts)
        self.assertIn("filter:rent:NO_LIMIT", callbacks)
        self.assertIn("filter:rent:600", callbacks)
        self.assertIn("✖ Cancel", texts)
        self.assertIn("tap the button below", _rent_prompt())

    def test_setup_step_keyboard_has_navigation(self) -> None:
        self.assertEqual(
            [button.text for button in _wbs_keyboard().inline_keyboard[-1]],
            ["✖ Cancel"],
        )
        self.assertEqual(
            [button.text for button in _location_keyboard(include_back=True).inline_keyboard[-1]],
            ["⬅ Back", "✖ Cancel"],
        )

    def test_setup_keyboard_marks_current_selection(self) -> None:
        texts = [
            button.text
            for row in _wbs_keyboard(selected="WBS 140").inline_keyboard
            for button in row
        ]
        self.assertIn("✓ WBS 140", texts)

    def test_filter_choice_keyboards_have_valid_callbacks(self) -> None:
        callback_data = [
            button.callback_data
            for keyboard in (_wbs_keyboard(), _location_keyboard(), _rent_keyboard(), _rooms_keyboard())
            for row in keyboard.inline_keyboard
            for button in row
        ]
        self.assertEqual(len(callback_data), 35)
        self.assertTrue(all(value for value in callback_data))
        self.assertTrue(all(len(value.encode("utf-8")) <= 64 for value in callback_data))
        self.assertTrue(all(value.startswith("filter:") for value in callback_data))

    def test_direct_admin_alert_keeps_triage_contract(self) -> None:
        self.assertEqual(
            self._inline_button_texts(_ai_qa_feedback_keyboard(123)),
            ["Parser error", "Parser correct", "Borderline / unsure"],
        )


class FilterPromptLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_filter_callback_redirects_without_reopening_setup(self) -> None:
        callback = _FakeCallback("settings:filter")
        state = _FakeState()
        await state.update_data(existing_preferences={"wbs_type": "WBS 140"})

        await handle_legacy_product_callback(callback, state)

        self.assertEqual(state.data, {})
        self.assertEqual(
            callback.answered,
            [("This prototype now uses one guided demo.", True)],
        )
        text, markup = callback.message.answered[-1]
        self.assertIn("Replay the guided scenario", text)
        self.assertEqual(markup.inline_keyboard[0][0].text, "See the product flow")

    async def test_no_matches_names_the_limited_catalog_boundary(self) -> None:
        message = _FakeMessage()
        with patch(
            "main.load_user_preferences",
            return_value=UserPreferences(wbs_type="WBS 140"),
        ), patch("main.enrich_missing_transport_walk"), patch(
            "main.load_active_filtered_match_candidates",
            return_value=[],
        ), patch(
            "main._verified_active_matches",
            new=AsyncMock(return_value=[]),
        ):
            await send_active_filtered_matches(message, _FakeBot(), user_id=123)

        text, markup = message.answered[-1]
        self.assertIn("limited synthetic demo catalog", text)
        self.assertIn("does not describe the live Berlin housing market", text)
        self.assertEqual(
            [button.text for row in markup.inline_keyboard for button in row],
            ["Edit filter", "See the product flow"],
        )

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

        location_callback = _FakeCallback("filter:location:Treptow-Köpenick")
        location_callback.message = wbs_callback.message
        await handle_location_choice(location_callback, state)
        self.assertEqual(state.data["location"], "Treptow-Köpenick")
        self.assertEqual(state.data["_state"], FilterSetup.choosing_rent)

        rent_callback = _FakeCallback("filter:rent:NO_LIMIT")
        rent_callback.message = location_callback.message
        await handle_rent_choice(rent_callback, state)
        self.assertIsNone(state.data["max_rent"])
        self.assertEqual(state.data["_state"], FilterSetup.choosing_rooms)

        rooms_callback = _FakeCallback("filter:rooms:3")
        rooms_callback.message = rent_callback.message
        with patch("main.save_fixed_preferences") as save_fixed_preferences, patch(
            "main.get_settings"
        ) as get_settings:
            get_settings.return_value = SimpleNamespace(bot_background_enabled=False)
            await handle_rooms_choice(rooms_callback, state)

        save_fixed_preferences.assert_called_once()
        self.assertEqual(state.data, {})
        self.assertIn("Filter saved.", rooms_callback.message.edited[-1][0])


if __name__ == "__main__":
    unittest.main()
