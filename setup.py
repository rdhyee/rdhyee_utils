from setuptools import setup, find_packages
import sys, os

version = '0.1.7'

setup(name='rdhyee_utils',
      version=version,
      description="Some simple methods and classes Raymond Yee developed for his own work.",
      long_description="""\
Some simple methods and classes Raymond Yee developed for his own work.""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='utilities',
      author='Raymond Yee',
      author_email='raymond.yee@gmail.com',
      url='https://github.com/rdhyee/rdhyee_utils',
      download_url="https://github.com/rdhyee/rdhyee_utils/tarball/0.1.7",
      license='Apache 2.0',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
