from openerp import models, fields, api, _
from datetime import datetime
#from openerp import toolsdefefewfc


class tk_resource_calendar_attendance(models.Model):
	_inherit = 'resource.calendar.attendance'

	month =  fields.Selection([(1, 'January'),(2,'February'),(3, 'March'),(4,'April'),(5, 'May'),(6,'June'),(7,'July'),(8, 'August'),(9,'September'),(10,'October'),(11, 'November'),(12,'December')])
