#coding=utf-8
import os
import shutil
from dataroom.models import dataroomdirectoryorfile
from dataroom.views import makeDirWithdirectoryobjs, getPathWithFile
from third.views.qiniufile import downloadFileToPath
from utils.somedef import encryptPdfFilesWithPassword, zipDirectory, addWaterMarkToPdfFiles





# def downloadDataroomFiles(folder_path, file_ids, directory_ids):
#     # 建立dataroom各级文件夹
#     directory_qs = dataroomdirectoryorfile.objects.filter(id__in=directory_ids, is_deleted=False)
#     makeDirWithdirectoryobjs(directory_qs, folder_path)
#     # 下载dataroom文件到对应文件夹下
#     file_qs = dataroomdirectoryorfile.objects.filter(id__in=file_ids, is_deleted=False)
#     filepaths = []
#     for file_obj in file_qs:
#         path = getPathWithFile(file_obj, folder_path)
#         downloadFileToPath(key=file_obj.realfilekey, bucket=file_obj.bucket, path=path)
#         if os.path.exists(path):
#             filetype = path.split('.')[-1]
#             if filetype in ['pdf', u'pdf']:
#                 filepaths.append(path)
#     return filepaths
#
#
#
# def func_makeDataroomZipFile(arguments):
#
#     folder_path = arguments.get('folder_path')
#     password = arguments.get('password')
#
#     file_ids = arguments.get('file_ids')
#     directory_ids = arguments.get('directory_ids')
#     virtual = arguments.get('virtual')
#     virtual = None if virtual else virtual.replace('@', '[at]').split(',')
#
#     filepaths = downloadDataroomFiles(folder_path, file_ids, directory_ids)
#     addWaterMarkToPdfFiles(filepaths, virtual)
#     encryptPdfFilesWithPassword(folder_path, password)
#     zipDirectory(folder_path)


def downloadDataroomFiles(folder_path, file_qs, directory_qs):
    # 建立dataroom各级文件夹
    makeDirWithdirectoryobjs(directory_qs, folder_path)
    # 下载dataroom文件到对应文件夹下
    filepaths = []
    for file_obj in file_qs:
        path = getPathWithFile(file_obj, folder_path)
        downloadFileToPath(key=file_obj.realfilekey, bucket=file_obj.bucket, path=path)
        if os.path.exists(path):
            filetype = path.split('.')[-1]
            if filetype in ['pdf', u'pdf']:
                filepaths.append(path)
    return filepaths



def func_makeDataroomZipFile(arguments):

    folder_path = arguments.get('folder_path')
    password = arguments.get('password')

    file_qs = arguments.get('file_qs')
    directory_qs = arguments.get('directory_qs')
    virtual = arguments.get('virtual')

    filepaths = downloadDataroomFiles(folder_path, file_qs, directory_qs)
    addWaterMarkToPdfFiles(filepaths, virtual)
    encryptPdfFilesWithPassword(folder_path, password)
    zipDirectory(folder_path)