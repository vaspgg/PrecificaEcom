import threading
import time
import webbrowser
import uvicorn
from app.database import init_db

def server():
    uvicorn.run('app.main:app',host='127.0.0.1',port=8765,log_level='warning')

if __name__=='__main__':
    init_db()
    threading.Thread(target=server,daemon=True).start()
    time.sleep(1.2)
    webbrowser.open('http://127.0.0.1:8765')
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        pass
