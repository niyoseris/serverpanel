import unittest
from app import create_app, db
from app.models import User, Project
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'

class UserModelCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username='susan')
        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_project_creation(self):
        p = Project(name='test_project', port=5000, domain='example.com', path='/tmp/test')
        db.session.add(p)
        db.session.commit()
        self.assertEqual(Project.query.count(), 1)
        self.assertEqual(Project.query.first().name, 'test_project')

if __name__ == '__main__':
    unittest.main()
