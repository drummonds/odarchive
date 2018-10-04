from fabric.api import task, local, lcd
from os import remove, walk
from os.path import join
import re

@task
def clean():
    """remove all build, test, coverage and Python artifacts"""
    clean_build()
    clean_pyc()
    clean_test()


def find_and_remove_tree(path, match):
    return path+match


def clean_file(filename):
    try:
        remove(filename)
    except FileNotFoundError:
        pass


def find_and_remove_file(path, match):
    regex = re.compile(match)
    for root, dirs, files in walk(path, topdown=False):
        for name in files:
            if regex.match(name):
                print('deleting file {}'.format(join(root, name)))
        # for name in dirs:
        #    print(join(root, name))


def clean_build():
    """remove build artifacts"""
    #remove_tree(('build/', 'dist/', '.eggs/'))
    find_and_remove_tree('.', '.egg-info$')
    find_and_remove_file('.', '.egg$')


def clean_pyc():
    """remove Python file artifacts"""
    find_and_remove_file('.', '.pyc$')
    find_and_remove_file('.', '.pyo$')
    find_and_remove_file('.', '~$')
    find_and_remove_file('.', '__pycache__$')


def clean_test():
    """remove test and coverage artifacts"""
    #remove_tree(('build/', '.tox/', 'htmlcov/'))
    clean_file('.coverage')


@task
def build():
    """builds source and wheel package"""
    clean()
    local('python setup.py sdist')
    local('python setup.py bdist_wheel')
    #dir_list('dist')


@task
def release():
    """package and upload a release"""
    build()
    local('twine upload --repository pypi dist/*')
    #local('python setup.py bdist_wheel upload')


@task
def release_test():
    """package and upload a release"""
    build()
    local('twine upload --repository testpypi dist/*')
    #local('python setup.py bdist_wheel upload -r testpypi')

@task
def make_docs():
    """Create documentation"""
    assert False, "Not yet implemented"
    with lcd('docs'):
        ## generate Sphinx HTML documentation, including API docs
        try:
            remove('docs/odarchive.rst')
        except FileNotFoundError:
            pass
        try:
            remove('docs/modules.rst')
        except FileNotFoundError:
            pass
        local('sphinx-apidoc -o . ../odarchive')
        # $ (MAKE) - C         docs         clean
        local('make html')
        # $(BROWSER)    docs / _build / html / index.html


