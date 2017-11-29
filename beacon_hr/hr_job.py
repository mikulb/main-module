from openerp import models, fields, api, tools

class edit_hr_job(models.Model):
	_inherit = 'hr.job'

	@api.onchange('department_id')
	def get_department_id(self):
		if self.department_id:
			self.user_id = self.department_id.manager_id.user_id.id

class edit_resource_calendar_attendance(models.Model):
	_inherit = "resource.calendar.attendance"

	day_off = fields.Boolean(string="Day Off", default=False)