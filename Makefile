all: 
	make arc
	make sloth

arc: *.py
	python3 setup.py install

sloth: *.py
	cd sloth && python3 setup.py install && cd ..