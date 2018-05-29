from setuptools import setup

setup(name="sf_dia",
      version="1.4.0",
      maintainer="Paul Scherrer Institute",
      maintainer_email="daq@psi.ch",
      author="Paul Scherrer Institute",
      author_email="daq@psi.ch",
      description="SwissFEL Jungfrau detector integration",

      license="GPL3",

      packages=['sf_dia',
                'sf_dia.client']
      )
