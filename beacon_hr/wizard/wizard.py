from datetime import datetime, date, time, timedelta
from openerp import models, fields, api
from openerp.exceptions import except_orm, Warning, RedirectWarning
from openerp import tools
import math

import pdfkit, base64, xlsxwriter
from tempfile import TemporaryFile
#import pandas as pd

class attendance_report(models.TransientModel):
	_name = 'attendance.report'

	name = fields.Many2one('hr.employee',string='Employee Name')
	date_from = fields.Date(string='Date From')
	date_to = fields.Date(string='Date To')
	output_type = fields.Selection([('pdf', 'Portable Document (pdf)')], string='Report format', help='Choose the format for the output', default='pdf', required=True)

	@api.multi
	def print_report(self, data, context=None):

		if context is None:
			context = {}

		current_user = self.env.user
	#print current_user.name

		values = {
				'type': 'ir.actions.report.xml',
				'report_name': 'attendance.report',
				'datas': {
						'output_type': self.output_type,
						'variables': {
							'd_from' : self.date_from,
							'd_to' : self.date_to,
							'id' : self.name.id,
							'name' : self.name.name,
							'user' : current_user.name,
						}
					},
				}	
		return values

class all_overtime_report(models.TransientModel):
	_name = 'all.overtime.report'

	date = fields.Date(string='Date')
	output_type = fields.Selection([('pdf', 'Portable Document (pdf)')], string='Report format', help='Choose the format for the output', default='pdf', required=True)

	@api.multi
	def print_report(self, data, context=None):

		if context is None:
			context = {}

		current_user = self.env.user
	#print current_user.name

		query = """ SELECT
						SUBSTRING(to_char(aor.date, 'Month'),1,3) As mm,
						SUBSTRING(to_char(aor.date, 'yyyy'),1,4) yy
					FROM all_overtime_report aor WHERE aor.id = %s """ % (self.id)
		self.env.cr.execute(query)
		data = self.env.cr.fetchall()
		for time in data:
			mm = time[0]
			yy = time[1]

		values = {
				'type': 'ir.actions.report.xml',
				'report_name': 'all.overtime.report',
				'datas': {
						'output_type': self.output_type,
						'variables': {
							'mm' : mm,
							'yy' : yy,
							'user' : current_user.name,
						}
					},
				}	
		return values

class payroll_summary_report(models.TransientModel):
	_name = 'payroll.summary.report'

	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string="Date To")
	selection = fields.Selection([('a','All Employees'),('b','Employees Who Filed Overtime Only')], default='b')
	output_type = fields.Selection([('pdf', 'Portable Document (pdf)'),('xls', 'Excel Spreadsheet (xls)')], string='Report format', help='Choose the format for the output', default='pdf', required=True)

	@api.multi
	def print_report(self, data, context=None):

		if context is None:
			context = {}

		current_user = self.env.user
	#print current_user.name

		values = {
				'type': 'ir.actions.report.xml',
				'report_name': 'payroll.summary.report.wizard',
				'datas': {
						'output_type': self.output_type,
						'variables': {
							'date_from' : self.date_from,
							'date_to' : self.date_to,
							'ids' : self.id,
							'user' : current_user.name,
						}
					},
				}	
		return values

class timesheet_per_employee(models.TransientModel):
	_name = 'timesheet.per.employee.line'

	timesheet_id = fields.Many2one('timesheet.per.employee', 'timesheet_line')
	tardy = fields.Char(string="Tardy")
	undertime = fields.Char(string="Undertime")
	overtime = fields.Char(string="Overtime")

class timesheet_per_employee(models.TransientModel):
	_name = 'timesheet.per.employee'

	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string="Date To")
	name = fields.Many2one('hr.employee',string='Employee Name')

	output_type = fields.Selection([('pdf', 'Portable Document (pdf)')], string='Report format', help='Choose the format for the output', default='pdf', required=True)

	message_text = fields.Text(string="Message", readonly=True)
	excel_file = fields.Binary(string='Excel File')

	timesheet_line = fields.One2many('timesheet.per.employee.line', 'timesheet_id')

	'''
	@api.multi
	def print_report(self, data, context=None):

		if context is None:
			context = {}

		current_user = self.env.user
	#print current_user.name

		values = {
				'type': 'ir.actions.report.xml',
				'report_name': 'timesheet.employee.report.wizard',
				'datas': {
						'output_type': self.output_type,
						'variables': {
							'date_from' : self.date_from,
							'date_to' : self.date_to,
							'name_id' : self.name.id,
							'user' : current_user.name,
						}
					},
				}	
		return values
	'''
	@api.multi
	def leave_type_report_return(self):
		query = """ DELETE FROM timesheet_per_employee_line WHERE timesheet_id = %s """ % (self.id)
		self.env.cr.execute(query)
		return {
			'name': 'Timesheet Per Employee',
			'view_type': 'form',
			'view_mode': 'form',
			'view_id': self.env['ir.ui.view'].search([('name','=','Timesheet Per Employee')]).id,
			'res_model': 'timesheet.per.employee',
			'domain': [],
			'nodestroy': True,
			'context': None,
			'type': 'ir.actions.act_window',
			'target': 'new',
			'res_id': self.id
			}

	@api.multi
	def print_reports(self):

		query = """
			SELECT
				main.dates,
				main.e_name,
				main.d_name,
				main.p_name,
				main.d_days,
				Case When aa is null Then ( Case When ab is null Then ac Else ab End ) Else aa End As time_sched,
				Case main.d_state
					When 'a' Then 'Draft'
					When 'b' Then 'To be Approved'
					When 'c' Then 'Approved'
					When 'd' Then 'Cancelled'
					Else 'None'
				End As d_state,
				Case When main.s_in is null Then '00:00' Else main.s_in End As s_in,
				Case When main.s_out is null Then '00:00' Else main.s_out End As s_out,
				SUBSTRING(Case When aa is null Then ( Case When ab is null Then ac Else ab End ) Else aa End,1,5)::Varchar As ts_in,
				SUBSTRING(Case When aa is null Then ( Case When ab is null Then ac Else ab End ) Else aa End,7,11)::Varchar As ts_out,

				Case
					When main.d_type is null Then ( Case When ( Case When aa is null Then ( Case When ab is null Then ac Else ab End ) Else aa End is not null ) Then 'Regular Working Day' Else 'Day Off' End )
					Else main.d_type
				End As types,

				round( Cast(main.overtime  As NUMERIC),2) As overtime,
				main.late,
				main.leaves

			From (
				Select
					to_char(i, 'mm-dd-yyyy') As dates,
					( Select he.name_related From hr_employee he Where he.id = %s ) As e_name,
					( Select ( Select hd.name From hr_department hd Where hd.id = he.department_id ) From hr_employee he Where he.id = %s ) As d_name,
					( Select he.position From hr_employee he Where he.id = %s ) As p_name,
					SUBSTRING(to_char(i::timestamp, 'Day'),1,3) As d_days,

					(	SELECT
							SUBSTRING(ha.transmission_date::Timestamp::Varchar,12,5)
						From hr_attendance ha
						Where ha.employee_id = %s
							And SUBSTRING(ha.transmission_date,1,10)::date in (i)
							And ha.action like 'sign_in'
						Order By ha.transmission_date::date Asc
						Limit 1
					) As s_in,

					(	SELECT
							SUBSTRING(ha.transmission_date::Timestamp::Varchar,12,5)
						From hr_attendance ha
						Where ha.employee_id = %s
							And SUBSTRING(ha.transmission_date,1,10)::date in (i)
							And ha.action like 'sign_out'
						Order By ha.transmission_date::date Asc
						Limit 1
					) As s_out,

					( EXTRACT(MONTH FROM i)::INT ) As trim,
					(	SELECT
							Concat(to_char(to_timestamp((rca.hour_from) * 60), 'MI:SS'),
							'-',
							to_char(to_timestamp((rca.hour_to) * 60), 'MI:SS'))
						From hr_contract hc
						Left Join resource_calendar rc On rc.id = hc.working_hours
						Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
						Where hc.employee_id = %s
							And hc.state in ('draft','open','to_renew')
							And rca.date_from = (i)
							Order by rca.date_from Asc, rca.month
							Limit 1
					) As aa,
					(	SELECT
							Concat(to_char(to_timestamp((rca.hour_from) * 60), 'MI:SS'),
							'-',
							to_char(to_timestamp((rca.hour_to) * 60), 'MI:SS'))
						From hr_contract hc
						Left Join resource_calendar rc On rc.id = hc.working_hours
						Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
						Where hc.employee_id = %s
							And hc.state in ('draft','open','to_renew')
							And rca.date_from is null
							And rca.month in ( EXTRACT(MONTH FROM i)::INT )
							And rca.dayofweek in ( Case SUBSTRING(to_char(i::date, 'Day'),1,3)
														When 'Mon' Then '0'
														When 'Tue' Then '1'
														When 'Wed' Then '2'
														When 'Thu' Then '3'
														When 'Fri' Then '4'
														When 'Sat' Then '5'
														Else '6'
													End )
							Order by rca.date_from Asc, rca.month
							Limit 1
					) As ab,
					(	SELECT
							Concat(to_char(to_timestamp((rca.hour_from) * 60), 'MI:SS'),
							'-',
							to_char(to_timestamp((rca.hour_to) * 60), 'MI:SS'))
						From hr_contract hc
						Left Join resource_calendar rc On rc.id = hc.working_hours
						Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
						Where hc.employee_id = %s
							And hc.state in ('draft','open','to_renew')
							And rca.date_from is null
							And rca.month is null
							And rca.dayofweek in ( Case SUBSTRING(to_char(i::date, 'Day'),1,3)
														When 'Mon' Then '0'
														When 'Tue' Then '1'
														When 'Wed' Then '2'
														When 'Thu' Then '3'
														When 'Fri' Then '4'
														When 'Sat' Then '5'
														Else '6'
													End )
							Order by rca.date_from Asc, rca.month
							Limit 1
					) As ac,

					(	Select
							CASE ch.category
								WHEN 'legal' THEN 'Legal Holiday'
								WHEN 'special_non_working' THEN 'Special Non-Working Holiday'
								WHEN 'school' THEN  'School Holiday'
								ELSE NULL
							END
						From custom_holidays ch Where ch.date in (i::DATE) Limit 1
					) as d_type,

					(	Select
							/*
							Sum((
								((SUBSTRING((os.duration + interval '8 Hours')::Timestamp::Varchar,12,2)::Float*60) + SUBSTRING((os.duration + interval '8 Hours')::Timestamp::Varchar,15,2)::Float)
							-
								((SUBSTRING((os.start_time + interval '8 Hours')::Timestamp::Varchar,12,2)::Float*60) + SUBSTRING((os.start_time + interval '8 Hours')::Timestamp::Varchar,15,2)::Float)
							) / 60)
							*/
							SUM(EXTRACT(EPOCH FROM os.duration) - EXTRACT(EPOCH FROM os.start_time)) / 3600
						From overtime_slip os
						Where os.name = %s
							And to_char((os.start_time + interval '8 hour')::date, 'yyyy-MM-dd') in (to_char(i::date,'yyyy-MM-dd'))
							And os.state like 'c'
					)	As overtime,

					(	Select os.state
						From overtime_slip os
						Where os.name = %s
							And to_char((os.start_time + interval '8 hour')::date, 'yyyy-MM-dd') in (to_char(i::date,'yyyy-MM-dd'))
							And os.state like 'c'
						Order By os.create_date
						Desc Limit 1
					)	As d_state,

					(	Select cl.late
						From hr_employee he
						Left Join config_late cl On cl.employee_internal_category = he.employee_internal_category
						Where he.id = %s
							And cl.active_late = 't'
						Limit 1
					)::float As late,

					(	SELECT
							Case
								When hh.number_of_days > -1 Then Concat( 'Half Day', ' ',
									Case hh.state
										When 'confirm' Then '( To Approve )'
										When 'refuse' Then '( Refused )'
										When 'validate' Then '( Approved )'
										Else '( To Submit )'
									End )
								Else Concat( ( Select hhs.name From hr_holidays_status hhs Where hhs.id = hh.holiday_status_id ),' ',
									Case hh.state
										When 'confirm' Then '( To Approve )'
										When 'refuse' Then '( Refused )'
										When 'validate' Then '( Approved )'
										Else '( To Submit )'
									End )
							End
						FROM hr_holidays hh
						WHERE employee_id = %s
							And i::timestamp::date BETWEEN (hh.date_from + interval '8 hour')::timestamp::date AND (hh.date_to + interval '8 hour')::timestamp::date
							And hh.state = 'validate'
							Order by hh.date_from
						Limit 1
					) As leaves

				From generate_series('%s'::date,'%s'::date,'1 day'::interval) i
			) As main
		""" % (self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.name.id, self.date_from, self.date_to)
		self.env.cr.execute(query)
		result = self.env.cr.dictfetchall()

		html = """
			<div id='table_holder' style="width: 100%; text-align:center;">
				<table style="margin: 0 auto; text-align:center;">
					<tr>
						<th style=" width: 150px; height: 40px; background: rgb(249, 249, 249); text-align: center; border:1px solid black; border-collapse: collapse;">DATE</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">DAYS</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">TYPE</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center;  border:1px solid black; border-collapse: collapse;">TIME SCHEDULE</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center;  border:1px solid black; border-collapse: collapse;">TIME IN</th>
						<th style=" background: rgb(249, 249, 249); width: 120px; text-align: center;  border:1px solid black; border-collapse: collapse;">TIME OUT</th>
						<th style=" background: rgb(249, 249, 249); width: 95px; text-align: center;  border:1px solid black; border-collapse: collapse;">TARDY</th>
						<th style=" background: rgb(249, 249, 249); width: 95px; text-align: center;  border:1px solid black; border-collapse: collapse;">UNDERTIME</th>
						<th style=" background: rgb(249, 249, 249); width: 95px; text-align: center;  border:1px solid black; border-collapse: collapse;">OVERTIME</th>
						<th style=" background: rgb(249, 249, 249); width: 95px; text-align: center;  border:1px solid black; border-collapse: collapse;">REMARKS</th>
					</tr> """

		output = TemporaryFile('w+')
		workbook = xlsxwriter.Workbook(output)
		columns = [desc[0] for desc in self._cr.description]
		worksheet = workbook.add_worksheet("Employee Timesheet Data")

		row = col = 0
		worksheet.write_row(row, col, ('Beacon School', '', '', '', '', '', '', ''))
		row += 1
		worksheet.write_row(row, col, ('Timesheet Per Emploee', '', '', '', '', '', '', ''))
		row += 1
		worksheet.write_row(row, col, ('Name Of Employee: ', self.name.name_related, '', '', '', '', '', ''))
		row += 2
		worksheet.write_row(row, col, ('Date Generated:', (datetime.now()+timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'), '', '', '', '', '', ''))
		row += 2
		worksheet.write_row(row, col, ('DATE', 'DAYS', 'TYPE', 'TIME SCHEDULE', 'TIME IN', 'TIME OUT', 'TARDY', 'UNDERTIME','OVERTIME','REMARKS'))

		collection = []
		for rows in result:
			collection.append(rows)

		for this in collection:

			if this['types'] == 'Regular Working Day':
				time_sched = this['time_sched']
			else:
				time_sched = 'Flexi Time'

			if this['leaves'] == None:
				leaves = this['d_state']
			else:
				leaves = this['leaves']

			if this['ts_in'] is None:
				ts_in = "00:00"
			else:
				ts_in = this['ts_in']

			if this['ts_out'] is None:
				ts_out = "00:00"
			else:
				ts_out = this['ts_out']

			# TOTAL HOUR FOR UNDERTIME
			# WHEN ACTUAL TIME IN IS STILL 00:00
			if this['s_out'] == '00:00':
				out = '00:00'
			else:
				out = ts_out

			x1 = this['s_out'][0:2]
			y1 = this['s_out'][3:5]
			x2 = out[0:2]
			y2 = out[3:5]

			xy1 = ( int(x1) * 60 ) + int(y1)
			xy2 = ( int(x2) * 60 ) + int(y2)
			xy3 = xy2 - xy1
			xy4 = (xy3)/60
			xy5 = xy3 - (xy4 * 60)

			# Hours
			if this['leaves'] != None:
				xy6 = '00'
			elif xy4 <= -1:
				xy6 = '00'
			elif xy4 <= 9:
				xy6 = '0'+str(xy4)
			else:
				xy6 = xy4

			# Minutes
			if this['leaves'] != None:
				xy7 = '00'
			elif xy4 <= -1:
				xy7 = '00'
			elif xy5 <= 9:
				xy7 = '0'+str(xy5)
			else:
				xy7 = xy5

			undertime = "%s:%s" % (xy6,xy7)
			# TOTAL HOUR FOR TARDY
			t1 = ts_in[0:2]
			q1 = ts_in[3:5]
			t2 = this['s_in'][0:2]
			q2 = this['s_in'][3:5]

			tq1 = ( int(t1) * 60 ) + int(q1)
			tq2 = ( int(t2) * 60 ) + int(q2)
			tq3 = tq2 - tq1
			tq4 = (tq3)/60
			tq5 = tq3 - (tq4 * 60)

			# Hours
			if time_sched == 'Flexi Time':
				tq6 = '00'
			elif tq4 <= -1:
				tq6 = '00'
			elif tq4 <= 9:
				tq6 = '0'+str(tq4)
			else:
				tq6 = tq4

			# Minutes
			if time_sched == 'Flexi Time':
				tq7 = '00'
			elif tq4 <= -1 or (tq4 <= 0 and tq5 <= this['late']):
				tq7 = '00'
			elif tq5 <= 9:
				tq7 = '0'+str(tq5)
			else:
				tq7 = tq5

			tardy = "%s:%s" % (tq6,tq7)

			# DISPLAY TARDY
			if time_sched == 'Flexi Time':
				time_tardy = '00:00'
			elif this['leaves'] != None:
				time_tardy = '00:00'
			else:
				time_tardy = tardy

			# DISPLAY UNDERTIME
			if time_sched == 'Flexi Time':
				time_undertime = '00:00'
			elif this['leaves'] != None:
				time_undertime = '00:00'
			else:
				time_undertime = undertime

			# TOTAL HOUR FOR OVERTIME
			if this['overtime'] == None:
				overtime_x = "00:00"
				overtime_y = "0"
			else:
				overtime_x = this['overtime']
				overtime_y = this['overtime']

			# INSERT INTO LINES
			tt1 = time_tardy[0:2]
			tt2 = time_tardy[3:5]
			tt3 = (int(tt1)*60)+int(tt2)

			uu1 = time_undertime[0:2]
			uu2 = time_undertime[3:5]
			uu3 = (int(uu1)*60)+int(uu2)

			'''
			oo1 = overtime[0:2]
			oo2 = overtime[3:5]
			oo3 = (int(oo1)*60)+int(oo2)
			'''
			oo3 = overtime_y

			insert_query = """ INSERT INTO timesheet_per_employee_line (timesheet_id, tardy, undertime, overtime) Values (%s, '%s', '%s', '%s') """ % (self.id, tt3, uu3, oo3)
			self.env.cr.execute(insert_query)

			row += 1
			worksheet.write_row(row, col, (this['dates'],this['d_days'],this['types'],time_sched,this['s_in'],this['s_out'],time_tardy,time_undertime,overtime_x,leaves))

			html = html + """
					<tr>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
					""" % (this['dates'],this['d_days'],this['types'],time_sched,this['s_in'],this['s_out'],time_tardy,time_undertime,overtime_x,leaves)
	
		get_query = """SELECT Sum(tardy::Int) As a, Sum(undertime::Int) As b, round( Cast( Sum(overtime::Float) As numeric),2) As c From timesheet_per_employee_line Where timesheet_id = %s """ % (self.id)
		self.env.cr.execute(get_query)
		get = self.env.cr.dictfetchall()
		for x in get:
			tt4 = x['a'] # Tardy
			uu4 = x['b'] # Undertime
			oo4 = x['c'] # Overtime

			# TOTAL HOURS OF ALL LINE FOR TARDY
			tt5 = (tt4)/60
			tt6 = tt4 - (tt5 * 60)

			if tt5 <= 9:
				tt7 = '0'+str(tt5)
			else:
				tt7 = tt5

			if tt6 <= 9:
				tt8 = '0'+str(tt6)
			else:
				tt8 = tt6
			tt9 = "%s:%s" % (tt7,tt8)

			# TOTAL HOURS OF ALL LINE FOR UNDERTIME
			uu5 = (uu4)/60
			uu6 = uu4 - (uu5 * 60)

			if uu5 <= 9:
				uu7 = '0'+str(uu5)
			else:
				uu7 = uu5

			if uu6 <= 9:
				uu8 = '0'+str(uu6)
			else:
				uu8 = uu6
			uu9 = "%s:%s" % (uu7,uu8)
			'''
			# TOTAL HOURS OF ALL LINE FOR OVERTIME
			oo5 = (oo4)/60
			oo6 = oo4 - (oo5 * 60)

			if oo5 <= 9:
				oo7 = '0'+str(oo5)
			else:
				oo7 = oo5

			if oo6 <= 9:
				oo8 = '0'+str(oo6)
			else:
				oo8 = oo6
			oo9 = "%s:%s" % (oo7,oo8)
			'''

			html = html + """
				<tr>
					<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;"></td>
					<td style="vertical-align: middle; text-align: center; height:30px;  border:1px solid black; border-collapse: collapse;"></td>
					<td style="vertical-align: middle; text-align: center; height:30px;  border:1px solid black; border-collapse: collapse;"></td>
					<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;"></td>
					<td style="vertical-align: middle; text-align: center; height:30px;  border:1px solid black; border-collapse: collapse;"></td>
					<td style="vertical-align: middle; text-align: center; height:30px;  border:1px solid black; border-collapse: collapse;">TOTAL</td>
					<td style="vertical-align: middle; text-align: center; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
					<td style="vertical-align: middle; text-align: center; height:30px;  border:1px solid black; border-collapse: collapse;">%s</td>
					<td style="vertical-align: middle; text-align: center; height:30px;  border:1px solid black; border-collapse: collapse;">%s</td>
					<td style="vertical-align: middle; text-align: center; height:30px;  border:1px solid black; border-collapse: collapse;"></td>
				</tr> """ % (tt9,uu9,oo4)
		html = html + """
				</table>
			</div>"""

		self.message_text = html

		row += 1
		worksheet.write_row(row, col, ('', '', '', '', '','TOTAL', tt9, uu9, oo4))

		workbook.close()
		output.seek(0)
		cy = output.read()
			
		#Write to odoo database
		self.write({'excel_file':base64.encodestring(cy)})

		return {
			'name': 'Timesheet Per Employee for '+ str(self.name.name),
			'view_type': 'form',
			'view_mode': 'form',
			'view_id': self.env['ir.ui.view'].search([('name','=','timesheet.per.employee.warning')]).id,
			'res_model': 'timesheet.per.employee',
			'domain': [],
			'nodestroy': True,
			'context': None,
			'type': 'ir.actions.act_window',
			'target': 'new',
			'res_id': self.id
			}

	@api.multi
	def download_excel(self):
		for rec in self:
			return {
					'type' : 'ir.actions.act_url',
					'url': '/web/binary/download_document?model=timesheet.per.employee&field=excel_file&id=%s&filename=%s'%(rec.id,"timesheet_per_employee.xls"),
					'target': 'self',
					}

	@api.multi
	def download_pdf(self):
		for rec in self:
			return {
					'type' : 'ir.actions.act_url',
					'url': '/web/binary/download_document?model=timesheet.per.employee&field=pdf_file&id=%s&filename=%s'%(rec.id,"timesheet_per_employee.pdf"),
					'target': 'self',
					}

class ea_substitution_report(models.TransientModel):
	_name = 'ea.substitution.report'

	name = fields.Char()
	date_from = fields.Date()
	date_to = fields.Date()

	days = fields.Selection([('a','1-15'),('b','16-31')])

	excel_file = fields.Binary(string='Excel File')
	message_text = fields.Text(string="Message", readonly=True)

	output_type = fields.Selection([('pdf', 'Portable Document (pdf)')], string='Report format', help='Choose the format for the output', default='pdf', required=True)

	@api.multi
	def substitution_report_return(self):

		return {
			'name': 'Substitution Summary',
			'view_type': 'form',
			'view_mode': 'form',
			'view_id': self.env['ir.ui.view'].search([('name','=','Substitution Summary')]).id,
			'res_model': 'ea.substitution.report',
			'domain': [],
			'nodestroy': True,
			'context': None,
			'type': 'ir.actions.act_window',
			'target': 'new',
			'res_id': self.id }

	@api.multi
	def print_report(self):
		DATETIME_FORMAT = "%Y-%m-%d"
		i1 = self.date_from
		i2 = datetime.strptime(i1, DATETIME_FORMAT)

		query_day = """SELECT DATE_PART('days',DATE_TRUNC('month', esr.date_from) + '1 MONTH'::INTERVAL - '1 DAY'::INTERVAL)::Int As a FROM ea_substitution_report esr Where esr.id in (%s)""" % (self.id)
		self.env.cr.execute(query_day)
		day = self.env.cr.dictfetchall()
		for x in day:
			date = x['a']
		print date
		
		if self.days == 'a':
			a0 = i2
			a1 = i2 + timedelta(days=1)
			a2 = i2 + timedelta(days=2)
			a3 = i2 + timedelta(days=3)
			a4 = i2 + timedelta(days=4)
			a5 = i2 + timedelta(days=5)
			a6 = i2 + timedelta(days=6)
			a7 = i2 + timedelta(days=7)
			a8 = i2 + timedelta(days=8)
			a9 = i2 + timedelta(days=9)
			a10 = i2 + timedelta(days=10)
			a11 = i2 + timedelta(days=11)
			a12 = i2 + timedelta(days=12)
			a13 = i2 + timedelta(days=13)
			a14 = i2 + timedelta(days=14)
			a15 = i2 + timedelta(days=15)
		elif self.days == 'b':
			a0 = i2 + timedelta(days=15)
			a1 = i2 + timedelta(days=16)
			a2 = i2 + timedelta(days=17)
			a3 = i2 + timedelta(days=18)
			a4 = i2 + timedelta(days=19)
			a5 = i2 + timedelta(days=20)
			a6 = i2 + timedelta(days=21)
			a7 = i2 + timedelta(days=22)
			a8 = i2 + timedelta(days=23)
			a9 = i2 + timedelta(days=24)
			a10 = i2 + timedelta(days=25)
			a11 = i2 + timedelta(days=26)
			a12 = i2 + timedelta(days=27)
			a13 = i2 + timedelta(days=28)
			a14 = i2 + timedelta(days=29)
			a15 = i2 + timedelta(days=30)
		else:
			a0 = []
			a1 = []
			a2 = []
			a3 = []
			a4 = []
			a5 = []
			a6 = []
			a7 = []
			a8 = []
			a9 = []
			a10 = []
			a11 = []
			a12 = []
			a13 = []
			a14 = []
			a15 = []

		c0 = str(a0)
		x0 = c0[5:10]

		c1 = str(a1)
		x1 = c1[5:10]

		c2 = str(a2)
		x2 = c2[5:10]

		c3 = str(a3)
		x3 = c3[5:10]

		c4 = str(a4)
		x4 = c4[5:10]

		c5 = str(a5)
		x5 = c5[5:10]

		c6 = str(a6)
		x6 = c6[5:10]

		c7 = str(a7)
		x7 = c7[5:10]

		c8 = str(a8)
		x8 = c8[5:10]

		c9 = str(a9)
		x9 = c9[5:10]

		c10 = str(a10)
		x10 = c10[5:10]

		c11 = str(a11)
		x11 = c11[5:10]

		c12 = str(a12)
		x12 = c12[5:10]

		c13 = str(a13)
		x13 = c13[5:10]

		c14 = str(a14)
		x14 = c14[5:10]

		c15 = str(a15)
		x15 = c15[5:10]

		query = """
				SELECT
					he.name_related AS name,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a0,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a1,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a2,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a3,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a4,


					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a5,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a6,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a7,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a8,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a9,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a10,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a11,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a12,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a13,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a14,

					(	SELECT
							COALESCE(SUM
								( CASE
									WHEN tss.selection = 'a' THEN 0.50
									WHEN tss.selection = 'b' THEN 1
									ELSE 0
								END ),0)::Float
						FROM teacher_substitution_slip tss
						WHERE tss.name in (he.id)
							AND tss.state = 'c'
							AND '%s'::timestamp::DATE BETWEEN (tss.DATE + interval '8 hour')::timestamp::DATE AND (tss.DATE_to + interval '8 hour')::timestamp::DATE
							AND selection in ('a','b')
					) As a15

				FROM hr_employee he
				WHERE he.active = 't'
					AND he.id in ( SELECT tss.name FROM teacher_substitution_slip tss WHERE tss.state = 'c' AND ((tss.date + interval '8 Hours')::timestamp >= '%s'::timestamp AND (tss.date_to + interval '8 Hours')::timestamp <= '%s'::timestamp ) GROUP BY tss.id )
				""" % (a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15, a0, a15)
		self.env.cr.execute(query)
		get = self.env.cr.dictfetchall()

		if self.days == 'a':
			d13 = x13
			d14 = x14
			d15 = "-"
		elif date == 30 and self.days == 'b':
			d13 = x13
			d14 = x14
			d15 = "-"
		elif date == 29 and self.days == 'b':
			d13 = x13
			d14 = "-"
			d15 = "-"
		elif date == 28 and self.days == 'b':
			d13 = "-"
			d14 = "-"
			d15 = "-"
		else:
			d13 = x13
			d14 = x14
			d15 = x15

		html = """
			<div id='table_holder' style="width: 100%; text-align:center;">
				<table style="margin: 0 auto; text-align:center;">
					<tr>
						<th style=" width: 150px; height: 40px; background: rgb(249, 249, 249); text-align: center; border:1px solid black; border-collapse: collapse;">Name</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{0}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{1}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{2}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{3}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{4}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{5}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{6}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{7}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{8}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{9}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{10}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{11}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{12}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{13}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{14}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">{15}</th>
						<th style=" background: rgb(249, 249, 249); width: 150px; text-align: center; border:1px solid black; border-collapse: collapse;">Total</th>
					</tr> """.format(x0,x1,x2,x3,x4,x5,x6,x7,x8,x9,x10,x11,x12,d13,d14,d15)

		output =  TemporaryFile('w+')
		workbook = xlsxwriter.Workbook(output)
		columns = [desc[0] for desc in self._cr.description]
		worksheet = workbook.add_worksheet("Substitution Report Summary")

		row = col = 0
		worksheet.write_row(row, col, ('Beacon School', '', '', '', '', '', '', ''))
		row += 1
		worksheet.write_row(row, col, ('Subsitution Summary', '', '', '', '', '', '', ''))
		row += 2
		worksheet.write_row(row, col, ('Date Generated:', (datetime.now()+timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'), '', '', '', '', '', ''))
		row += 2
		worksheet.write_row(row, col, ('Name', x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, d13, d14, d15))

		collection = []
		for rows in get:
			collection.append(rows)

		for this in collection:
			if self.days == 'a':
				day13 = this['a13']
				day14 = this['a14']
				day15 = '-'
			elif date == 30 and self.days == 'b':
				day13 = this['a13']
				day14 = this['a14']
				day15 = '-'
			elif date == 29 and self.days == 'b':
				day13 = this['a13']
				day14 = "-"
				day15 = "-"
			elif date == 28 and self.days == 'b':
				day13 = "-"
				day14 = "-"
				day15 = "-"
			else:
				day13 = this['a13']
				day14 = this['a14']
				day15 = this['a15']

			dy13 = str(day13).replace("-", "0")
			dy14 = str(day14).replace("-", "0")
			dy15 = str(day15).replace("-", "0")

			total = ( this['a0'] + this['a1'] + this['a2'] + this['a3'] + this['a4'] + this['a5'] + this['a6'] + this['a7'] + this['a8'] + this['a9'] + this['a10'] + this['a11'] + this['a12']  + float(dy13) + float(dy14) + float(dy15) )
#			total = ( float(this['a0']) + float(this['a1']) + float(this['a2']) + float(this['a3']) + float(this['a4']) + float(this['a5']) + float(this['a6']) + float(this['a7']) + float(this['a8']) + float(this['a9']) + float(this['a10']) + float(this['a11']) + float(this['a12'])  + float(dy13) + float(dy14) + float(dy15) )
			print total
			html = html + """
					<tr>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
						<td style="vertical-align: middle; text-align: center; padding: 3px; height:30px; border:1px solid black; border-collapse: collapse;">%s</td>
					""" % (this['name'], this['a0'], this['a1'], this['a2'], this['a3'], this['a4'], this['a5'], this['a6'], this['a7'], this['a8'], this['a9'], this['a10'], this['a11'], this['a12'], day13, day14, day15, total)

			row += 1
			worksheet.write_row(row, col, (this['name'], this['a0'], this['a1'], this['a2'], this['a3'], this['a4'], this['a5'], this['a6'], this['a7'], this['a8'], this['a9'], this['a10'], this['a11'], this['a12'], day13, day14, day15, total))

		workbook.close()
		output.seek(0)
		cy = output.read()

		#Write to odoo database
		self.write({'excel_file':base64.encodestring(cy)})

		html = html + """
				</table>
			</div>"""

		self.message_text = html

		return {
			'name': 'Substitution Report',
			'view_type': 'form',
			'view_mode': 'form',
			'view_id': self.env['ir.ui.view'].search([('name','=','ea.substitution.summary.warning')]).id,
			'res_model': 'ea.substitution.report',
			'domain': [],
			'nodestroy': True,
			'context': None,
			'type': 'ir.actions.act_window',
			'target': 'new',
			'res_id': self.id
			}

	@api.multi
	def download_excel(self):
		for rec in self:
			return {
					'type' : 'ir.actions.act_url',
					'url': '/web/binary/download_document?model=ea.substitution.report&field=excel_file&id=%s&filename=%s'%(rec.id,"ea_substitution_report.xls"),
					'target': 'self',
					}






























'''
class ea_substitution_reports(models.TransientModel):
	_name = 'ea.substitution.reports'

	name = fields.Char()
	date_from = fields.Date()
	date_to = fields.Date()

	days = fields.Selection([('a','1-15'),('b','15-31')])

	excel_file = fields.Binary(string='Excel File')
	message_text = fields.Text(string="Message", readonly=True)
	test = fields.Text(string="TEST")

	output_type = fields.Selection([('pdf', 'Portable Document (pdf)')], string='Report format', help='Choose the format for the output', default='pdf', required=True)

	@api.multi
	def substitution_report_return(self):

		return {
			'name': 'Substitution Summart',
			'view_type': 'form',
			'view_mode': 'form',
			'view_id': self.env['ir.ui.view'].search([('name','=','Substitution Summarys')]).id,
			'res_model': 'ea.substitution.reports',
			'domain': [],
			'nodestroy': True,
			'context': None,
			'type': 'ir.actions.act_window',
			'target': 'new',
			'res_id': self.id }

	@api.multi
	def print_report(self):

		query = """
					SELECT to_char(i,'yyyy-MM-dd') As a, to_char(i,'MM-dd-yyyy') As b FROM generate_series('%s'::date,'%s'::date,'1 day'::interval) i
				""" % (self.date_from, self.date_to)
		self.env.cr.execute(query)
		get = self.env.cr.dictfetchall()

		buffer = []
		for row in get:
			values = (row['a'],row['b'])
			buffer.append(values)       

		for i in range(len(buffer)):
			for j in range(len(buffer[0])):
				w = len(buffer)
		print w

		for i in range(len(buffer[0])):
			for j in range(len(buffer)):
				x = ([buffer[j][i] for j in range(len(buffer))])

		x1 = str(x).replace("u", "")
		x2 = str(x1).replace("[", "")
		x3 = str(x2).replace("]", "")
		self.test = x3
		print x3

		output =  TemporaryFile('w+')
		workbook = xlsxwriter.Workbook(output)
		columns = [desc[0] for desc in self._cr.description]
		worksheet = workbook.add_worksheet("Substitution Report Summary")

		row = col = 0
		worksheet.write_row(row, col, ('Beacon School', '', '', '', '', '', '', ''))
		row += 1
		worksheet.write_row(row, col, ('Subsitution Summary', '', '', '', '', '', '', ''))
		row += 2
		worksheet.write_row(row, col, ('Date Generated:', (datetime.now()+timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'), '', '', '', '', '', ''))
		row += 2
		worksheet.write_row(row, col, ('Name'))

		collection = []
		for rows in get:
			collection.append(rows)

		for this in collection:
			row += 1
			worksheet.write_row(row, col, '')

		workbook.close()
		output.seek(0)
		cy = output.read()

		#Write to odoo database
		self.write({'excel_file':base64.encodestring(cy)})

		return {
			'name': 'Substitution Report',
			'view_type': 'form',
			'view_mode': 'form',
			'view_id': self.env['ir.ui.view'].search([('name','=','ea.substitution.summary.warnings')]).id,
			'res_model': 'ea.substitution.reports',
			'domain': [],
			'nodestroy': True,
			'context': None,
			'type': 'ir.actions.act_window',
			'target': 'new',
			'res_id': self.id
			}

	@api.multi
	def download_excel(self):
		for rec in self:
			return {
					'type' : 'ir.actions.act_url',
					'url': '/web/binary/download_document?model=ea.substitution.reports&field=excel_file&id=%s&filename=%s'%(rec.id,"ea_substitution_report.xls"),
					'target': 'self',
					}

'''
