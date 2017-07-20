from setuptools import setup, find_packages

setup(
    name='arclimb',
    version='0.1.0',
    packages=find_packages(),
    license='Creative Commons Attribution-Noncommercial-Share Alike license',
    requires=['networkx', 'cv2', 'PyQt5', 'scipy', 'numpy', 'PyQt4'],
    entry_points={
        'console_scripts': [
            'pairtagger = arclimb.annotator:run_gui',
        ],
    }
)
