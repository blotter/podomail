#!/usr/bin/python3
# -*- encoding: utf8 -*-

"""
Copyright (C) 2013 Dan Luedtke <mail@danrl.de>

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


import os
import sys
import re
import sqlite3
from Crypto.Hash import SHA512
# wir moechten salzen
import binascii

### config
filename = "/etc/podomail.sqlite3"
salt = binascii.b2a_hex(os.urandom(5)).decode("ascii")


### functions
def check_email(email):
	# rfc 3696 allows much more than the following regex, which just tests
	# for general plausability
	if re.match(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]+$", email):
		return True
	return False

def split_email(email):
	name, sep, domain = email.partition("@")
	return name, domain

def usage():
	basename = os.path.basename(sys.argv[0])
	print("usage: "+ basename +" domain  show")
	print("       "+ basename +" mailbox show")
	print("       "+ basename +" mailbox add  <email> [password]")
	print("       "+ basename +" mailbox del  <email>")
	print("       "+ basename +" forward show")
	print("       "+ basename +" forward add  <src email> <dst email>")
	print("       "+ basename +" forward del  <src email> <dst email>")
	print("       "+ basename +" export  dovecot.passwd")
	print("       "+ basename +" export  postfix.mailbox_domains")
	print("       "+ basename +" export  postfix.mailbox_maps")
	print("       "+ basename +" export  postfix.alias_maps")
	sys.exit(1)

def error(msg):
	sys.stderr.write("error: " + msg + "\n")
	sys.exit(1)


### open database
try:
	con = sqlite3.connect(filename)
except e:
	print("database error: %s", e.args[0])
	sys.exit(1)
finally:
	cur = con.cursor()
	cur.executescript("""
		CREATE TABLE IF NOT EXISTS mailboxes (
			name TEXT,
			domain TEXT,
			password TEXT
		);
		CREATE UNIQUE INDEX IF NOT EXISTS idx_mailboxes ON mailboxes (
			name,
			domain
		);
		CREATE TABLE IF NOT EXISTS forwards (
			src_name TEXT,
			src_domain TEXT,
			dst_name TEXT,
			dst_domain TEXT
		);
		CREATE UNIQUE INDEX IF NOT EXISTS idx_forwards ON forwards (
			src_name,
			src_domain,
			dst_name,
			dst_domain
		);
	""")
	con.commit()


### domain show
if   len(sys.argv) > 2 and sys.argv[1] == 'domain' and sys.argv[2] == 'show':
	cur.execute("SELECT domain FROM mailboxes GROUP BY domain")
	for item in cur.fetchall():
		print(item[0])


### mailbox show
elif len(sys.argv) > 2 and sys.argv[1] == 'mailbox' and sys.argv[2] == 'show':
	cur.execute("SELECT name, domain FROM mailboxes ORDER BY domain")
	for item in cur.fetchall():
		print(item[0] + "@" + item [1])


### forward show
elif len(sys.argv) > 2 and sys.argv[1] == 'forward' and sys.argv[2] == 'show':
	cur.execute("SELECT src_name, src_domain, dst_name, dst_domain FROM \
		forwards ORDER BY dst_domain, dst_name, src_domain, src_name")
	for item in cur.fetchall():
		print(item[0] + "@" + item [1] \
			+ " -> " + \
			item[2] + "@" + item[3])


### mailbox add
elif len(sys.argv) > 3 and sys.argv[1] == 'mailbox' and sys.argv[2] == 'add':
	# email
	email = sys.argv[3]
	if not check_email(email):
		error("invalid email")
	name, domain = split_email(email)
	
	# fetch/read password
	if len(sys.argv) > 4:
		password = sys.argv[4]
	else:
		password = input("password: ")
	password = password.strip()
	if len(password) < 8:
		error("password too short")
		sys.exit(1)
	password += salt

	# generate hash of password
	sha = SHA512.new(password.encode('ascii', 'ignore'))
	# re-use password variable
	password = sha.hexdigest()

	# update database
	cur.execute("INSERT OR REPLACE INTO mailboxes(name, domain, password) \
		VALUES('"+ name +"', '"+ domain +"', '"+ password +"');")
	if cur.rowcount < 1:
		error("add failed")
	con.commit()


### mailbox del
elif len(sys.argv) > 3 and sys.argv[1] == 'mailbox' and sys.argv[2] == 'del':
	# email
	email = sys.argv[3]
	if not check_email(email):
		error("invalid email")
	name, domain = split_email(email)

	# update database
	cur.execute("DELETE FROM mailboxes WHERE name IS '"+ name +"' AND \
		domain IS '"+ domain +"';")
	if cur.rowcount < 1:
		error("del failed")
	con.commit()


### forward add
elif len(sys.argv) > 4 and sys.argv[1] == 'forward' and sys.argv[2] == 'add':
	# source email
	src = sys.argv[3]
	if not check_email(src):
		error("invalid src email")
	src_name, src_domain = split_email(src)
	
	# destination email
	dst = sys.argv[4]
	if not check_email(dst):
		error("invalid dst email")
	dst_name, dst_domain = split_email(dst)

	# disable forward to self
	if src_name == dst_name and src_domain == dst_domain:
		error("src same as dst")

	# update database
	cur.execute("INSERT OR REPLACE INTO \
		forwards(src_name, src_domain, dst_name, dst_domain) VALUES( \
		'" + src_name + "', '" + src_domain + "', \
		'" + dst_name + "', '" + dst_domain + "');")
	if cur.rowcount < 1:
		error("add failed")
	con.commit()


### forward del
elif len(sys.argv) > 4 and sys.argv[1] == 'forward' and sys.argv[2] == 'del':
	# source email
	src = sys.argv[3]
	if not check_email(src):
		error("invalid src email")
	src_name, src_domain = split_email(src)
	
	# destination email
	dst = sys.argv[4]
	if not check_email(dst):
		error("invalid dst email")
	dst_name, dst_domain = split_email(dst)

	# update database
	cur.execute("DELETE FROM forwards WHERE \
		src_name IS '" + src_name + "' AND \
		src_domain IS '" + src_domain + "' AND \
		dst_name IS '" + dst_name + "' AND \
		dst_domain IS '" + dst_domain + "';")
	if cur.rowcount < 1:
		error("del failed")
	con.commit()


### export dovecot.passwd
elif len(sys.argv) > 2 and sys.argv[1] == 'export' and \
	sys.argv[2] == 'dovecot.passwd':
	cur.execute("SELECT name, domain, password FROM mailboxes ORDER BY domain")
	for item in cur.fetchall():
		print(item[0] + "@" + item [1] + ":{SHA512.hex}" + item[2])


### export postfix.mailbox_domains
elif len(sys.argv) > 2 and sys.argv[1] == 'export' and \
	sys.argv[2] == 'postfix.mailbox_domains':

	# domains with mailboxes
	cur.execute("SELECT domain FROM mailboxes GROUP BY domain")
	items = cur.fetchall()

	# domains with forwards
	cur.execute("SELECT src_domain FROM forwards GROUP BY src_domain")
	items += cur.fetchall()

	# uniqify
	items = list(set(items))

	# print
	for item in items:
		print(item[0] + " OK")

### export postfix.mailbox_maps
elif len(sys.argv) > 2 and sys.argv[1] == 'export' and \
	sys.argv[2] == 'postfix.mailbox_maps':

	# mailboxes
	cur.execute("SELECT name, domain FROM mailboxes GROUP BY domain")
	items = cur.fetchall()

	# print
	for item in items:
		print(item[0] + "@" + item[1] + " OK")

### export postfix.alias_maps
elif len(sys.argv) > 2 and sys.argv[1] == 'export' and \
	sys.argv[2] == 'postfix.alias_maps':
	# regular forwards
	cur.execute("SELECT src_name, src_domain FROM forwards \
		GROUP BY src_domain, src_name")
	sources = cur.fetchall()
	for src in sources:
		destinations = ""
		cur.execute("SELECT dst_name, dst_domain FROM forwards WHERE \
			src_name IS '" + src[0] + "' AND \
			src_domain IS '" + src[1] + "';")
		for dst in cur.fetchall():
			destinations += " " + dst[0] + "@" + dst[1]
		print(src[0] + "@" + src[1] + destinations)

	# mailboxes refer to self, they must appear at last
	cur.execute("SELECT name, domain FROM mailboxes")
	for item in cur.fetchall():
		print(item[0] + "@" + item [1] + " " + item[0] + "@" + item[1])


### print usage information on unknown command
else:
	usage()




### exit clean
if con:
	con.close()
sys.exit(0)
