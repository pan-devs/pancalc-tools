una vez ya he hecho el [windows]

PS C:\Users\Adrin> pcalc eject
  PanCalc Tools v0.1.5  ·  󰻟 fx-CG50  (3+14 files)
  ────────────────────────────────────────────


  Ejecting fx-CG50 at E:[/]...Traceback (most recent call last):
  File "<frozen runpy>", line 203, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Scripts\pcalc.exe\__main__.py", line 5, in <module>
    sys.exit(cli())
             ~~~^^
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\click\core.py", line 1524, in __call__
    return self.main(*args, **kwargs)
           ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\click\core.py", line 1445, in main
    rv = self.invoke(ctx)
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\click\core.py", line 1912, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\click\core.py", line 1308, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\click\core.py", line 877, in invoke
    return callback(*args, **kwargs)
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\click\decorators.py", line 93, in new_func
    return ctx.invoke(f, obj, *args, **kwargs)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\click\core.py", line 877, in invoke
    return callback(*args, **kwargs)
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\pcalc\cli.py", line 1060, in cmd_eject
    _eject(calc)
    ~~~~~~^^^^^^
  File "C:\Users\Adrin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\pcalc\cli.py", line 210, in _eject
    handle = win32file.CreateFile(
        f"\\.\\{drive}",
    ...<2 lines>...
        None, win32file.OPEN_EXISTING, 0, None
    )
pywintypes.error: (123, 'CreateFile', 'El nombre de archivo, el nombre de directorio o la sintaxis de la etiqueta del volumen no son correctos.')