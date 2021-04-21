import uwsgi
from utils import workerFunc
from uwsgidecorators import *


# def worker(arguments):
#     func_name = arguments.get(b'func_name').decode()
#     be_called_function = getattr(workerFunc, func_name)
#     be_called_function(arguments)
#     return uwsgi.SPOOL_OK
#
#
# # register the worker
# uwsgi.spooler = worker



@spool(pass_arguments=True)
def makeDataroomZipFile(arguments):
    func_name = arguments.get('func_name')
    be_called_function = getattr(workerFunc, func_name)
    be_called_function(arguments)

# uwsgi.spooler = makeDataroomZipFile