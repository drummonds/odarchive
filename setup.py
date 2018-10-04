from distutils.core import setup
from setuptools import setup, find_packages

# Get version variables
exec(open('odarchive/_version.py').read())

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

setup(
    name = 'odarchive',
    version = __version__,
    description = 'Convert file systems to archiveable ISO files',
    long_description=readme + '\n\n' + history,
    author=__author__,
    author_email=__email__,
    url='https://github.com/drummonds/odarchive',
    packages=find_packages(include=['odarchive']),
    include_package_data=True,
    #install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords = ['cdrom', 'dvd', 'bdrom', 'archive', 'odarchive'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    #tests_require=test_requirements,
    #setup_requires=setup_requirements,
    #entry_points={
    #    'console_scripts': ['fab-support=fab_support.command_line:main'],
    #}
)