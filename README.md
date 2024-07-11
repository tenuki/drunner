# drunner

## setup

 * create venv: `$ python -m venv venv`
 * install deps:
        * `$ . ./venv/bin/activate`
        * `(venv) $ pip install -r requirements` 
 * create db file:
        * `$ . ./venv/bin/activate`
        * `(venv) $ python model.py` 

## exec

 * open env and run worker:
        * `$ . ./venv/bin/activate`
        * `(venv) $ dramatiq runner -t 1 -p 1` 
            * one thread and one process
 * open env and run webapp:
        * `$ . ./venv/bin/activate`
        * `(venv) $ python app.py`
            * one thread and one process
 
## testing

 * open env and run worker:
        * `$ . ./venv/bin/activate`
        * `(venv) $ python tests.py`
   * run webapp to review test db:
          * `$ . ./venv/bin/activate`
          * `(venv) $ DB_NAME=drunner.test.sqlite.db python app.py`
 