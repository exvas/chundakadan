from hrms.hr.doctype.leave_application.leave_application import LeaveApplication


class CustomLeaveApplication(LeaveApplication):

    def validate(self):

        super().validate()

        self.sync_custom_status()


    def on_update(self):

        super().on_update()

        self.sync_custom_status()


    def sync_custom_status(self):

        mapping = {
            "Partially Approved": "Partially Approved",
            "Pending": "Pending",
            "Draft": "Draft",
            "Cancelled": "Cancelled",
            "Rejected": "Rejected",
            "Approved": "Approved"
        }

        if self.custom_approval_status in mapping:
            self.status = mapping[self.custom_approval_status]