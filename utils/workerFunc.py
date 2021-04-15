#coding=utf-8
from utils.somedef import encryptPdfFilesWithPassword, zipDirectory



def func_makeDataroomZipFile(arguments):

    folder_path = arguments.get(b'foler_path').decode()
    password = arguments.get(b'password').decode()

    encryptPdfFilesWithPassword(folder_path, password)
    zipDirectory(folder_path)