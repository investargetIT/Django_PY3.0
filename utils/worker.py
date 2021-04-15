import uwsgi



def worker(arguments):
    func_name = str(arguments.get('func_name'))


    module_name = __import__("utils.workerFunc")
    be_called_function = getattr(module_name, func_name)
    be_called_function(arguments)
    return uwsgi.SPOOL_OK


# register the worker
uwsgi.spooler = worker