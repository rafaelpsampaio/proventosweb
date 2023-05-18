from setuptools import setup

setup(name='proventosweb',
      version='0.81',
      description='Uma biblioteca para buscar proventos de ações na plataforma Status Invest',
      url='https://github.com/rafaelpsampaio/proventosweb',
      author='Rafael Sampaio',
      author_email='rafapsampaio@gmail.com',
      packages=['proventosweb'],
      install_requires=[
          'pandas',
          'datetime',
          'requests',
          'bs4',
          'numpy'
      ],
      zip_safe=False)
