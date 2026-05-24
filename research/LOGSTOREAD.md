PS C:\Users\Adrin> pip install --upgrade pancalc-tools
Requirement already satisfied: pancalc-tools in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (0.1.5)
Collecting pancalc-tools
  Downloading pancalc_tools-0.1.7-py3-none-any.whl.metadata (12 kB)
Requirement already satisfied: click>=8.1 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (8.4.1)
Requirement already satisfied: rich>=13.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (15.0.0)
Requirement already satisfied: questionary>=2.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (2.1.1)
Requirement already satisfied: requests>=2.31 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (2.34.2)
Requirement already satisfied: Pillow>=10.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (12.2.0)
Requirement already satisfied: pymupdf>=1.23 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (1.27.2.3)
Requirement already satisfied: platformdirs>=4.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (4.9.6)
Requirement already satisfied: textual>=8.2.7 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (8.2.7)
Requirement already satisfied: python-gnupg>=0.5.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from pancalc-tools) (0.5.6)
Requirement already satisfied: colorama in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from click>=8.1->pancalc-tools) (0.4.6)
Requirement already satisfied: prompt_toolkit<4.0,>=2.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from questionary>=2.0->pancalc-tools) (3.0.52)
Requirement already satisfied: wcwidth in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from prompt_toolkit<4.0,>=2.0->questionary>=2.0->pancalc-tools) (0.7.0)
Requirement already satisfied: charset_normalizer<4,>=2 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from requests>=2.31->pancalc-tools) (3.4.7)
Requirement already satisfied: idna<4,>=2.5 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from requests>=2.31->pancalc-tools) (3.16)
Requirement already satisfied: urllib3<3,>=1.26 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from requests>=2.31->pancalc-tools) (2.7.0)
Requirement already satisfied: certifi>=2023.5.7 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from requests>=2.31->pancalc-tools) (2026.5.20)
Requirement already satisfied: markdown-it-py>=2.2.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from rich>=13.0->pancalc-tools) (4.2.0)
Requirement already satisfied: pygments<3.0.0,>=2.13.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from rich>=13.0->pancalc-tools) (2.20.0)
Requirement already satisfied: mdurl~=0.1 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from markdown-it-py>=2.2.0->rich>=13.0->pancalc-tools) (0.1.2)
Requirement already satisfied: mdit-py-plugins in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from textual>=8.2.7->pancalc-tools) (0.6.1)
Requirement already satisfied: typing-extensions<5.0.0,>=4.4.0 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from textual>=8.2.7->pancalc-tools) (4.15.0)
Requirement already satisfied: linkify-it-py<3,>=1 in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from markdown-it-py[linkify]>=2.1.0->textual>=8.2.7->pancalc-tools) (2.1.0)
Requirement already satisfied: uc-micro-py in .\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages (from linkify-it-py<3,>=1->markdown-it-py[linkify]>=2.1.0->textual>=8.2.7->pancalc-tools) (2.0.0)
Downloading pancalc_tools-0.1.7-py3-none-any.whl (53 kB)
Installing collected packages: pancalc-tools
  Attempting uninstall: pancalc-tools
    Found existing installation: pancalc-tools 0.1.5
    Uninstalling pancalc-tools-0.1.5:
      Successfully uninstalled pancalc-tools-0.1.5
Successfully installed pancalc-tools-0.1.7
PS C:\Users\Adrin> pcalc
Traceback (most recent call last):
  File "<frozen runpy>", line 203, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Scripts\pcalc.exe\__main__.py", line 2, in <module>
    from pcalc.cli import cli
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\pcalc\cli.py", line 212
    handle = win32file.CreateFile(
    ^^^^^^
SyntaxError: expected 'except' or 'finally' block