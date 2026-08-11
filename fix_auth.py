import re
with open("backend/auth.py", "r") as f:
    c = f.read()

c = c.replace("from passlib.context import CryptContext", "import bcrypt")
c = re.sub(r'pwd_context\s*=\s*CryptContext[^\n]+', '', c)

c = re.sub(r'def verify_password[^\n]+\n\s+return pwd_context\.verify[^\n]+', 
           'def verify_password(plain, hashed):\n    try:\n        return bcrypt.checkpw(plain.encode(), hashed.encode())\n    except:\n        return False', c)

c = re.sub(r'def hash_password[^\n]+\n\s+return pwd_context\.hash[^\n]+', 
           'def hash_password(plain):\n    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()', c)

with open("backend/auth.py", "w") as f:
    f.write(c)

print("Fixed!")
