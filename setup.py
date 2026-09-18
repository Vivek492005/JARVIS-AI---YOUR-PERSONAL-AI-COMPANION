from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="access-os",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Unified Assistive Operating Environment for Windows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/access-os",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Adaptive Technologies",
        "Topic :: Desktop Environment",
    ],
    python_requires=">=3.10",
    install_requires=[
        'SpeechRecognition>=3.10.0',
        'pyttsx3>=2.90',
        'opencv-python>=4.7.0',
        'mediapipe>=0.9.0.2',
        'numpy>=1.21.0'
    ],
    entry_points={
        'console_scripts': [
            'access-os=access_os.main:main',
        ],
    },
    include_package_data=True,
)
