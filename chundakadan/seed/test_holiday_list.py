import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from chundakadan.seed.holiday_list import HOLIDAY_LIST_NAME, upsert_holidays

LIST_NAME = "CDN Test Holiday List"


class TestHolidaySeed(FrappeTestCase):
	"""HR deletes the holidays the office does not actually take. Re-adding
	every "missing" date on migrate put them all back, every time.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		if frappe.db.exists("Holiday List", LIST_NAME):
			frappe.delete_doc("Holiday List", LIST_NAME, force=True, ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def _seed(self, year):
		upsert_holidays(target_list=LIST_NAME, years=[year])
		return frappe.get_doc("Holiday List", LIST_NAME)

	def test_a_new_year_is_seeded(self):
		doc = self._seed(2027)
		self.assertTrue(doc.holidays)
		self.assertTrue(all(getdate(h.holiday_date).year == 2027 for h in doc.holidays))

	def test_a_deleted_holiday_stays_deleted(self):
		"""The whole point."""
		doc = self._seed(2027)
		victim = next(h for h in doc.holidays if not h.weekly_off)
		gone = getdate(victim.holiday_date)
		doc.set("holidays", [h for h in doc.holidays if getdate(h.holiday_date) != gone])
		doc.save(ignore_permissions=True)

		upsert_holidays(target_list=LIST_NAME, years=[2027])

		after = frappe.get_doc("Holiday List", LIST_NAME)
		self.assertNotIn(gone, [getdate(h.holiday_date) for h in after.holidays])

	def test_a_holiday_hr_added_themselves_survives(self):
		doc = self._seed(2027)
		doc.append("holidays", {"holiday_date": "2027-03-11", "description": "Shop anniversary"})
		doc.save(ignore_permissions=True)

		upsert_holidays(target_list=LIST_NAME, years=[2027])

		after = frappe.get_doc("Holiday List", LIST_NAME)
		self.assertIn(getdate("2027-03-11"), [getdate(h.holiday_date) for h in after.holidays])

	def test_running_it_again_changes_nothing(self):
		before = len(self._seed(2027).holidays)
		upsert_holidays(target_list=LIST_NAME, years=[2027])
		self.assertEqual(len(frappe.get_doc("Holiday List", LIST_NAME).holidays), before)

	def test_a_year_not_on_the_list_is_still_added(self):
		"""Leaving a year alone must not stop the next year arriving."""
		self._seed(2027)
		upsert_holidays(target_list=LIST_NAME, years=[2028])
		years = {getdate(h.holiday_date).year
		         for h in frappe.get_doc("Holiday List", LIST_NAME).holidays}
		self.assertEqual(years, {2027, 2028})

	def test_emptying_a_year_does_not_refill_it(self):
		"""HR clearing a year out is a decision, not a gap."""
		doc = self._seed(2027)
		doc.set("holidays", [h for h in doc.holidays if getdate(h.holiday_date).year != 2027])
		# inside the list's own range, which Frappe insists on
		doc.append("holidays", {"holiday_date": "2027-06-15", "description": "Shop day"})
		doc.save(ignore_permissions=True)

		upsert_holidays(target_list=LIST_NAME, years=[2027])

		after = frappe.get_doc("Holiday List", LIST_NAME)
		self.assertEqual(len(after.holidays), 1)
