from datetime import datetime, date, time, timedelta
from openerp import models, fields, api
from openerp.exceptions import except_orm, Warning, RedirectWarning
from openerp import tools

class overtime_slip(models.Model):
	_name = 'overtime.slip'
	_inherit = 'mail.thread'

	@api.multi
	def def_draft(self):
		self.state = 'a'

	@api.multi
	def def_to_approve(self):
		get = self.for_state()
		if get == 't':
			raise Warning("""Make sure you have Actual Time IN or Actual Time OUT before filing Overtime.""")
		else:
			self.state = 'b'

	@api.multi
	def def_approve(self):
		current_user = self.env.user
		get = self.for_state()

		if self.res_user.id == current_user.id:
			raise Warning("""You are not allowed to approve your own overtime.""")
		else:
			if get == 't':
				raise Warning("""You cannot approve this Overtime yet.\n The employee may not have the Time In or Time Out in the system.\n Please try to Generate Time again if the employee have the Time in and Time out.""")
			else:
				self.state = 'c'

	@api.multi
	def def_cancel(self):
		self.state = 'd'

	state = fields.Selection([('a','Draft'),('b','To Be Approved'),('c','Approved'),('d','Disapproved')], default='a', string='State', track_visibility='onchange')
	res_user = fields.Many2one('res.users', default=lambda self: self.env.user)
	name = fields.Many2one('hr.employee', string='Employee Name', required=True)
	date_filed = fields.Date(string='Date Filed', default = fields.Date.today(), readony=True)
	start_time = fields.Datetime(string='From', default= fields.Date.today(), required=True)
	duration = fields.Datetime(string='To', required=True)
	position = fields.Char(string='Position')
	department = fields.Many2one('hr.department', string='Department')
	purpose = fields.Text(string='Purpose of Overtime')
	department_head_id = fields.Many2one('res.users', string="Approver")
	approver_name = fields.Char(related='department_head_id.name', string="Approver")
	scheduled_in_time = fields.Char(string='Scheduled Time-IN', track_visibility='onchange')
	scheduled_out_time = fields.Char(string='Scheduled Time-OUT', track_visibility='onchange')
	actual_in_time = fields.Char(string='Actual Time-IN', track_visibility='onchange')
	actual_out_time = fields.Char(string='Actual Time-OUT', track_visibility='onchange')
	total_overitme = fields.Char(string="Total Overtime")
	total_overitme_filed = fields.Char(string="Total Overtime Filed")
	day = fields.Selection([
		('sun','Sunday'),
		('mon','Monday'),
		('tue','Tuesday'),
		('wed','Wednesday'),
		('thu','Thursday'),
		('fri','Friday'),
		('sat','Saturday')], string="Day")
	holiday_id = fields.Many2one('custom.holidays', string='Holiday')
	manager_comment = fields.Text(string='Manager Comment')
	employee_comment = fields.Text(string='Employee Comment')

	@api.onchange('res_user','name')
	def get_current_user(self):
		query = """ SELECT he.id FROM resource_resource rr
					Left Join hr_employee he On he.resource_id = rr.id
					Where rr.user_id = %s """ % (self.res_user.id)
		self.env.cr.execute(query)
		result = self.env.cr.dictfetchall()
		for this in result:
			self.name = this['id']

		self.position = self.name.job_id.name
		self.department = self.name.department_id.id
		self.department_head_id = self.name.parent_id.user_id

	@api.multi
	def get_time_out(self):
		DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
		i1 = self.start_time
		i2 = datetime.strptime(i1, DATETIME_FORMAT)
		i3 = i2 + timedelta(hours=8,minutes=00)

		self.holiday_id = False

		query = """
				SELECT
					d,
					main.holiday,
					COALESCE(
						Case When main.hour_from1 is null Then ( Case When main.hour_from2 is null Then main.hour_from3 Else main.hour_from2 End ) Else main.hour_from1 End,
					'00:00:00') As in_human,
					COALESCE(
						Case When main.hour_to1 is null Then ( Case When main.hour_to2 is null Then main.hour_to3 Else main.hour_to2 End ) Else main.hour_to1 End,
					'00:00:00')  As out_human,
					COALESCE(main.a_in,'00:00:00') As human_in,
					COALESCE(main.a_out,'00:00:00') As human_out,
					substring(to_char(main.d,'day'),1,3) As day,
					main.filed_ot,
					main.holiday_id
				From (
					SELECT
						'%s'::DATE AS d,
						(	SELECT
								SUBSTRING(ha.transmission_date::Timestamp::Varchar,12,8)
							From hr_attendance ha
							Where ha.employee_id = hc.employee_id
								And SUBSTRING(ha.transmission_date,1,10)::date = '%s'
								And ha.action like 'sign_in'
							Order By ha.transmission_date::date Asc
							Limit 1
						) As a_in,

						(	SELECT
								SUBSTRING(ha.transmission_date::Timestamp::Varchar,12,8)
							From hr_attendance ha
							Where ha.employee_id = hc.employee_id
								And SUBSTRING(ha.transmission_date,1,10)::date = '%s'
								And ha.action like 'sign_out'
							Order By ha.transmission_date::date Asc
							Limit 1
						) As a_out,

						(	SELECT
								to_char(to_timestamp((rca.hour_from) * 60), 'MI:SS:00')
							From hr_contract shc
								Left Join resource_calendar rc On rc.id = shc.working_hours
								Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
							Where shc.employee_id in (hc.employee_id)
								And shc.state in ('draft','open','to_renew')
								And rca.date_from in ('%s'::date)
							Order by rca.date_from Asc, rca.month
							Limit 1
						) As hour_from1,

						(	SELECT
								to_char(to_timestamp((rca.hour_from) * 60), 'MI:SS:00')
							From hr_contract shc
								Left Join resource_calendar rc On rc.id = shc.working_hours
								Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
							Where shc.employee_id in (hc.employee_id)
								And shc.state in ('draft','open','to_renew')
								And rca.date_from is null
								And rca.month in ( EXTRACT(MONTH FROM DATE '%s')::INT )
								And rca.dayofweek in ( Case SUBSTRING(to_char('%s'::date, 'Day'),1,3)
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
						) As hour_from2,

						(	SELECT
								to_char(to_timestamp((rca.hour_from) * 60), 'MI:SS:00')
							From hr_contract shc
								Left Join resource_calendar rc On rc.id = shc.working_hours
								Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
							Where shc.employee_id in (hc.employee_id)
								And shc.state in ('draft','open','to_renew')
								And rca.date_from is null
								And rca.month is null
								And rca.dayofweek in ( Case SUBSTRING(to_char('%s'::date, 'Day'),1,3)
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
						) As hour_from3,

						(	SELECT
								to_char(to_timestamp((rca.hour_to) * 60), 'MI:SS:00')
							From hr_contract shc
								Left Join resource_calendar rc On rc.id = shc.working_hours
								Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
							Where shc.employee_id in (hc.employee_id)
								And shc.state in ('draft','open','to_renew')
								And rca.date_from in ('%s'::date)
							Order by rca.date_from Asc, rca.month
							Limit 1
						) As hour_to1,

						(	SELECT
								to_char(to_timestamp((rca.hour_to) * 60), 'MI:SS:00')
							From hr_contract shc
								Left Join resource_calendar rc On rc.id = shc.working_hours
								Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
							Where shc.employee_id in (hc.employee_id)
								And shc.state in ('draft','open','to_renew')
								And rca.date_from is null
								And rca.month in ( EXTRACT(MONTH FROM DATE '%s')::INT )
								And rca.dayofweek in ( Case SUBSTRING(to_char('%s'::date, 'Day'),1,3)
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
						) As hour_to2,

						(	SELECT
								to_char(to_timestamp((rca.hour_to) * 60), 'MI:SS:00')
							From hr_contract shc
								Left Join resource_calendar rc On rc.id = shc.working_hours
								Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
							Where shc.employee_id in (hc.employee_id)
								And shc.state in ('draft','open','to_renew')
								And rca.date_from is null
								And rca.month is null
								And rca.dayofweek in ( Case SUBSTRING(to_char('%s'::date, 'Day'),1,3)
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
						) As hour_to3,

						COALESCE(
							(	SELECT
									CASE WHEN ch.id IS NOT NULL THEN 1 ELSE 0 END
								FROM custom_holidays ch
								WHERE ch.date = ('%s'::DATE)
									AND ch.implement = 't'
								LIMIT 1
							),
						0 ) As holiday,

						(	SELECT
								((EXTRACT(EPOCH FROM os.duration) - EXTRACT(EPOCH FROM os.start_time))  * INTERVAL '1 SECOND' )::VARCHAR
							FROM overtime_slip os WHERE os.id = %s
						) AS filed_ot,

						(	SELECT ch.id
							FROM custom_holidays ch
							WHERE ch.date::DATE IN ('%s'::DATE)
								AND ch.implement = 't'
							LIMIT 1
						) AS holiday_id

					From hr_contract hc
					Where hc.employee_id = %s And hc.state in ('draft','open','pending')
					Order By hc.create_date Desc
					Limit 1
				) As main
			""" % (i3, i3, i3, i3, i3, i3, i3, i3, i3, i3, i3, i3, self.id, i3, self.name.id)
		self.env.cr.execute(query)
		data = self.env.cr.fetchall()

		for datas in data:
			human_in = '%s %s' % (datas[0],datas[2])
			human_out = '%s %s' % (datas[0],datas[3])
			in_human = '%s %s' % (datas[0],datas[4])
			out_human = '%s %s' % (datas[0],datas[5])

			x1 = datetime.strptime(human_in, DATETIME_FORMAT)
			y1 = datetime.strptime(human_out, DATETIME_FORMAT)
			x2 = datetime.strptime(in_human, DATETIME_FORMAT)
			y2 = datetime.strptime(out_human, DATETIME_FORMAT)

			self.scheduled_in_time = x1
			self.scheduled_out_time = y1
			self.actual_in_time = x2
			self.actual_out_time = y2
			self.day = datas[6]
			self.holiday_id = datas[8]

		if (datas[2] or datas[3]) == '00:00:00' or datas[1] == 1:
			total = y2 - x2
			self.total_overitme = total
		else:
			total = y2 - y1
			self.total_overitme = total

		self.total_overitme_filed = datas[7]

	@api.multi
	def for_state(self):
		t2 = self.actual_out_time[11:19]
		t1 = self.actual_in_time[11:19]

		if t1 == '00:00:00' or t2 == '00:00:00':
			for_state = 't'
		else:
			for_state = 'f'
		return for_state

	'''
	@api.multi
	def get_time_out(self):

		self.scheduled_in_time = False
		self.scheduled_out_time = False

		DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
		i1 = self.start_time
		i2 = datetime.strptime(i1, DATETIME_FORMAT)
		i3 = i2 + timedelta(hours=8,minutes=00)
		i4 = str(i3)[11:16]

		o1 = self.duration
		o2 = datetime.strptime(o1, DATETIME_FORMAT)
		o3 = o2 + timedelta(hours=8,minutes=00)
		o4 = str(o3)[11:16]

		query = """ SELECT substring(to_char(i,'day'),1,3) As days From generate_series('%s', '%s', '1 day'::interval) i """ % (i3, i3)
		self.env.cr.execute(query)
		result = self.env.cr.fetchall()
		for results in result:
			self.day = results[0]

		scheduled = """
				SELECT
					Case When main.a_in is null Then '00:00' Else main.a_in End As human_in,
					Case When main.a_out is null Then '00:00' Else main.a_out End As human_out,
					Case
						When ( Case When aa is null Then ( Case When ab is null Then ac Else ab End ) Else aa End ) is null Then '00:00-00:00'
						Else Case When aa is null Then ( Case When ab is null Then ac Else ab End ) Else aa End
					End As s_time,
					Case When aa is null Then ( Case When ab is null Then ac Else ab End ) Else aa End As all,
					main.a_in,
					main.a_out,
					main.holiday
				From (
					SELECT
						(	SELECT
								SUBSTRING(ha.transmission_date::Timestamp::Varchar,12,5)
							From hr_attendance ha
							Where ha.employee_id = hc.employee_id
								And SUBSTRING(ha.transmission_date,1,10)::date = '%s'
								And ha.action like 'sign_in'
							Order By ha.transmission_date::date Asc
							Limit 1
						) As a_in,

						(	SELECT
								SUBSTRING(ha.transmission_date::Timestamp::Varchar,12,5)
							From hr_attendance ha
							Where ha.employee_id = hc.employee_id
								And SUBSTRING(ha.transmission_date,1,10)::date = '%s'
								And ha.action like 'sign_out'
							Order By ha.transmission_date::date Asc
							Limit 1
						) As a_out,

						(	SELECT
								Concat(to_char(to_timestamp((rca.hour_from) * 60), 'MI:SS'),
								'-',
								to_char(to_timestamp((rca.hour_to) * 60), 'MI:SS'))
							From hr_contract hc
								Left Join resource_calendar rc On rc.id = hc.working_hours
								Left Join resource_calendar_attendance rca On rca.calendar_id = rc.id
							Where hc.employee_id in (%s)
								And hc.state in ('draft','open','to_renew')
								And rca.date_from in ('%s'::date)
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
							Where hc.employee_id in (%s)
								And hc.state in ('draft','open','to_renew')
								And rca.date_from is null
								And rca.month in ( EXTRACT(MONTH FROM DATE '%s')::INT )
								And rca.dayofweek in ( Case SUBSTRING(to_char('%s'::date, 'Day'),1,3)
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
							Where hc.employee_id in (%s)
								And hc.state in ('draft','open','to_renew')
								And rca.date_from is null
								And rca.month is null
								And rca.dayofweek in ( Case SUBSTRING(to_char('%s'::date, 'Day'),1,3)
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

						COALESCE(
							(	SELECT
									CASE WHEN ch.id IS NOT NULL THEN 1 ELSE 0 END
								FROM custom_holidays ch
								WHERE ch.date = ('%s'::DATE)
									AND ch.implement = 't'
								LIMIT 1
							),
						0 ) As holiday

				From hr_contract hc
				Where hc.employee_id = %s And hc.state in ('draft','open','pending')
				Order By hc.create_date Desc
				Limit 1 ) As main
				""" % (i3, i3, self.name.id, i3, self.name.id, i3, i3, self.name.id, i3, i3, self.name.id)
		self.env.cr.execute(scheduled)
		data = self.env.cr.fetchall()

		current_user = self.env.user

		self.total_overitme_filed = self.total_overtime()

		for time in data:
			# Scheduled TIME IN AND TIME OUT 00:00-00:00
			x = time[2]
			x1 = x[0:5]
			y1 = x[6:11]

			# Scheduled TIME OUT 00:00
			z3 = y1[0:2]
			s3 = y1[3:5]
			zs2 = (int(z3)*60)+int(s3)

			# Actual TIME OUT 00:00
			z2 = time[1][0:2]
			s2 = time[1][3:5]
			zs1 = (int(z2)*60)+int(s2)

			# Actual TIME OUT - Scheduled TIME OUT
			zs3 = zs1-zs2

			if time[4] == None:
				self.actual_in_time = False
			else:
				self.actual_in_time = time[4]

			if time[5] == None:
				self.actual_out_time = False
			else:
				self.actual_out_time = time[5]

			self.scheduled_in_time = x1
			self.scheduled_out_time = y1

		if self.scheduled_in_time == False or self.scheduled_out_time == False or time[3] == None or time[6] == 1:
			print "========================"
			io1 = o3-i3
			io2 = str(io1)
			io3 = io2
			io4 = str(io3).replace(":", "")

			if int(io4) <= 99999:
				io5 = '0'+str(io4)
			else:
				io5 = io4

			io6 = io5[0:2]
			io7 = io5[2:4]
			io8 = "%s:%s" % (io6,io7)
			self.scheduled_in_time = i4
			self.scheduled_out_time = o4
			self.actual_in_time = i4
			self.actual_out_time = o4
			self.total_overitme = io8
		else:
			print "_======================_"
			if time[2] is None:
				hh1 = 0
			else:
				hh1 = zs3
			hh2 = hh1/60

			hh3 = hh1-(hh2*60)

			if hh3 == 0:
				hh4 = '00'
			elif hh3 <= 9 >= 1:
				hh4 = '0'+str(hh3)
			else:
				hh4 = hh3

			thh = str(hh2).replace("-", "")

			if time[5] == None:
				self.total_overitme = '00:00'
			elif float(hh2) <= -1:
				self.total_overitme = '-0'+str(thh)+':'+str(hh4)
			elif float(hh2) <= 9:
				self.total_overitme = '0'+str(thh)+':'+str(hh4)
			else:
				self.total_overitme = str(thh)+':'+str(hh4)
	'''

	@api.multi
	def update_total_time(self):
		hm15 = ()
		try:
			# Schedule Time Out
			hh2 = self.scheduled_out_time[0:2]
			mm2 = self.scheduled_out_time[3:5]
			hm2 = (int(hh2) * 60) + int(mm2)

			# Actual Time Out
			hh4 = self.actual_out_time[0:2]
			mm4 = self.actual_out_time[3:5]
			hm4 = (int(hh4) * 60) + int(mm4)

			if hm4 >= hm2:
				hm11 = hm4 - hm2
				hm12 = (hm4 - hm2)/60
				hm13 = hm11 - (hm12 * 60)
			else:
				hm11 = hm2 - hm4
				hm12 = (hm2 - hm4)/60
				hm13 = hm11 - (hm12 * 60)

			if hm13 == 0:
				hm14 = '00'
			elif hm13 <= 9 >= 1:
				hm14 = '0'+str(hm13)
			else:
				hm14 = hm13

			if float(hm12) <= 9:
				hm15 = '0'+str(hm12)+':'+str(hm14)
			else:
				hm15 = str(hm12)+':'+str(hm14)
		except:
			raise Warning("Error Updating Total Overtime Time \n Make sure the value of Schedule Time Out and Actual Time Out is in correct format 00:00.")
		self.total_overitme = hm15

class official_business_slip(models.Model):
	_name = 'official.business.slip'
	_inherit = 'mail.thread'

	@api.multi
	def def_draft(self):
		self.state = 'a'

	@api.multi
	def def_to_approve(self):
		t = "%Y-%m-%d %H:%M:%S"
		a1 = self.date
		a2 = datetime.strptime(a1, t)
		a3 = a2 + timedelta(hours=8,minutes=00)

		self.state = 'b'
		holiday_q = """ SELECT hhs.id From hr_holidays_status hhs Where hhs.name like 'Official Business Leave' Order By hhs.id Asc Limit 1 """
		self.env.cr.execute(holiday_q)
		data = self.env.cr.fetchall()

		for datas in data:
			print "------------"

		name = self.name.name +' Official Business'
		query = """ 
			INSERT INTO hr_holidays
			(	state,
				name,
				holiday_status_id,
				reason,
				date_from,
				date_to,
				holiday_type,
				employee_id,
				department_id,
				type,
				user_id,
				user_manager_id,
				number_of_days,
				number_of_days_temp,
				active,
				official_business,
				official_business_form_id
			)
			Values
			(	'confirm', -- state
				'%s', -- name -- name
				%s, -- holiday_status_id -- datas[0]
				'%s', -- reason -- self.purpose
				'%s', -- date_form -- self.date
				'%s', -- date_to -- self.date
				'employee', -- holiday_type
				%s, -- employee_id -- self.name.id
				%s, -- department_id -- self.name.department_id.id
				'remove', -- type
				%s, -- user_id -- self.res_user.id
				%s, -- user_manager_id -- self.department_head_id.id
				-1, -- number_of_days
				1, -- number_of_days_temp
				true, -- active
				true, -- official_business
				%s -- official_business_form_id -- self.id
			) 
		""" % (name, datas[0], self.purpose, a3, a3, self.name.id, self.name.department_id.id, self.res_user.id, self.department_head_id.id, self.id)
		self.env.cr.execute(query)

	@api.multi
	def def_approve(self):
		self.state = 'c'

	@api.multi
	def def_cancel(self):
		self.state = 'd'

	state = fields.Selection([('a','Draft'),('b','To Be Approved'),('c','Approved'),('d','Disapproved')], default='a', string='State', track_visibility='onchange')
	res_user = fields.Many2one('res.users', default=lambda self: self.env.user)
	name = fields.Many2one('hr.employee', string='Employee Name')
	department = fields.Many2one('hr.department', string='Department')
	date_filed = fields.Date(string='Date Filed', default = fields.Date.today(), readony=True)
	date = fields.Datetime(string='From')
	date_to = fields.Datetime(string='To')
	client_name = fields.Char(string='Client Name')
	client_address = fields.Char(string='Client Address')
	tel_num = fields.Char(string='Contact Number')
	purpose = fields.Text(string='Purpose')
	department_head_id = fields.Many2one('res.users', string="Approver")
	approver_name = fields.Char(related='department_head_id.name', string="Approver")

	@api.onchange('res_user')
	def get_current_user(self):
		query = """ SELECT he.id FROM resource_resource rr
					Left Join hr_employee he On he.resource_id = rr.id
					Where rr.user_id = %s """ % (self.res_user.id)
		self.env.cr.execute(query)
		result = self.env.cr.dictfetchall()
		for this in result:
			self.name = this['id']

		self.department = self.name.department_id.id
		self.approver_id = self.department.manager_id.id
		self.department_head_id = self.name.parent_id.user_id

class teacher_substitution_slip(models.Model):
	_name = 'teacher.substitution.slip'
	_inherit = 'mail.thread'

	@api.multi
	def def_draft(self):
		self.state = 'a'

	@api.multi
	def def_to_approve(self):

		if self.name == self.teacher_name:
			raise Warning("""Please select other teacher to substitute.""")
		elif self.selection is False:
			raise Warning("""Please Select Half Day or Full Day.""")
		else:
			self.state = 'b'

	@api.multi
	def def_approve(self):
		if self.selection is False:
			raise Warning("""The subtitution form need to select Half Day or Full Day""")
		else:
			self.state = 'c'

	@api.multi
	def def_cancel(self):
		self.state = 'd'

	state = fields.Selection([('a','Draft'),('b','To Be Approved'),('c','Approved'),('d','Disapproved')], default='a', string='State', track_visibility='onchange')
	res_user = fields.Many2one('res.users', default=lambda self: self.env.user)
	date_filed = fields.Date(string='Date Filed', default = fields.Date.today(), readony=True)
	date = fields.Datetime(string='Date From')
	date_to = fields.Datetime(string='Date To')
	selection = fields.Selection([('a','Half Day'),('b','Full Day')], string='Selection')
	name = fields.Many2one('hr.employee', string='Substitute Name')
	teacher_name = fields.Many2one('hr.employee', string='Substitute for')
	reason = fields.Text(string='Reason')
	department = fields.Many2one('hr.department', string='Department')
	department_head_id = fields.Many2one('res.users', string="Approver")
	approver_name = fields.Char(related='department_head_id.name', string="Approver")

	@api.onchange('res_user')
	def get_current_user(self):
		name_query = """ SELECT he.id FROM resource_resource rr
					Left Join hr_employee he On he.resource_id = rr.id
					Where rr.user_id = %s """ % (self.res_user.id)
		self.env.cr.execute(name_query)
		result = self.env.cr.dictfetchall()
		for this in result:
			self.name = this['id']
		substitute_name = {'domain':{'name':[('id','=',this['id'])] }}

		teacher_query = """ SELECT he.id FROM hr_employee he
							WHERE he.active = 't'
								AND he.employee_internal_category IN (
									SELECT eic.id
									FROM employee_internal_category eic
									WHERE eic.name LIKE 'Academic' )
							ORDER BY he.name_related ASC """
		self.env.cr.execute(teacher_query)
		data = self.env.cr.fetchall()
		teachers_name = {'domain':{'teacher_name':[('id','in',data)] }}

		self.department = self.name.department_id.id
		self.approver_id = self.department.manager_id.id
		self.department_head_id = self.name.parent_id.user_id

		return substitute_name and teachers_name
