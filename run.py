from app import create_app, db
from app.models import User, Project

import click

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Project': Project}

@app.cli.command("create-user")
@click.argument("username")
@click.argument("password")
def create_user(username, password):
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f"User {username} created.")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
