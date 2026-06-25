import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from main import delete_user_data
from flatfeed.db.models import Base, SentListingNotification, User


class UserDataTests(unittest.TestCase):
    def test_delete_user_data_removes_filter_and_notification_history(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

        with test_session() as session:
            session.add(User(user_id=123, raw_input="filter"))
            session.add(SentListingNotification(user_id=123, listing_id=1))
            session.add(SentListingNotification(user_id=456, listing_id=1))
            session.commit()

        with patch("main.SessionLocal", test_session):
            self.assertTrue(delete_user_data(123))

        with test_session() as session:
            self.assertIsNone(session.get(User, 123))
            remaining_notifications = list(
                session.scalars(select(SentListingNotification)).all()
            )
            self.assertEqual(len(remaining_notifications), 1)
            self.assertEqual(remaining_notifications[0].user_id, 456)

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
