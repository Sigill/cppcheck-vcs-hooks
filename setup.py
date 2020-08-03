import setuptools

with open("README.md", "r") as fh:
  long_description = fh.read()

with open('requirements.txt') as f:
  requirements = f.read().splitlines()

setuptools.setup(
    name="cppcheckvcsutils",
    version="0.0.1",
    author="Cyrille Faucheux",
    author_email="cyrille.faucheux@gmail.com",
    description="Utilities to write VCS hooks for cppcheck",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Sigill/cppcheck-vcs-utils",
    packages=setuptools.find_packages(),
    classifiers=[
      "Programming Language :: Python :: 2",
      "Programming Language :: Python :: 3",
      "Programming Language :: C++",
      "License :: OSI Approved :: MIT License",
      "Operating System :: OS Independent",
      "Topic :: Software Development :: Version Control ",
      ],
    python_requires='>=2.6',
    install_requires=requirements,
    scripts=['bin/cppcheck-diff-findings.py', 'bin/cppcheck-mercurial.py'],
    )
