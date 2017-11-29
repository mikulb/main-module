{
    'name': 'Overtime',
    'category': 'none',
    'summary': 'Filing Overtime',
    'version': '0.1',
    'description': """
OVERTIME
====================================
Custom Overtime Customizations
        """,
    'author': 'Toolkt Inc',
    'depends': ['base','hr','resource','pentaho_reports','hr_recruitment','attendance_monitor'],
    'demo': [
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'modules.xml',
        'report/report.xml',
        'wizard/wizard.xml',
        'hr_job.xml',
    ],
    'qweb': [

    ],
    'installable': True,
}