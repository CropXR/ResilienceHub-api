erd:
	python manage.py graph_models api -o erd.png -X AccessionCodeModel

migration:
	python manage.py makemigrations
	python manage.py migrate

devel:
	python manage.py runserver

superuser:
	python manage.py createsuperuser

test:
	python manage.py test

users:
	python manage.py create_testusers

reset:
	rm db.sqlite3
	make migration
	python manage.py create_testusers
	python manage.py create_testdata
