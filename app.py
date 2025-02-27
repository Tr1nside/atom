import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import io
import contextlib
import builtins

app = Flask(__name__)
app.config['SECRET_KEY'] = 'some_secret_key'
socketio = SocketIO(app)

# pending_inputs хранит ожидания ввода для каждого клиента по его sid.
pending_inputs = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('execute')
def execute_code(code):
    sid = request.sid

    def custom_input(prompt=""):
        # Отправляем запрос на ввод в консоль клиента
        socketio.emit("console_output", prompt, room=sid)
        # Создаем событие для ожидания ответа
        ev = eventlet.Event()
        pending_inputs[sid] = ev
        user_input = ev.wait()  # кооперативное ожидание ввода
        return user_input

    local_env = {}
    # Готовим окружение: переопределяем input на нашу функцию
    exec_globals = {"__builtins__": builtins.__dict__.copy()}
    exec_globals["input"] = custom_input

    output_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, exec_globals, local_env)
        result = output_buffer.getvalue()
        if not result.strip():
            result = "Код выполнен, но вывода не было."
    except Exception as e:
        result = f"Ошибка: {e}"

    socketio.emit('console_output', result, room=sid)

@socketio.on('console_input')
def handle_console_input(data):
    sid = request.sid
    if sid in pending_inputs:
        pending_inputs[sid].send(data)
        del pending_inputs[sid]
    else:
        socketio.emit('console_output', f"\n(Ввод вне запроса: {data})\n", room=sid)

if __name__ == '__main__':
    socketio.run(app, debug=True)
