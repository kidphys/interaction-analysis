import sys

sys.argv = [*sys.argv, '--server.port', '8502']

from abu_dhabi_university.abu_dhabi_university_dashboard import render_dashboard

render_dashboard()
