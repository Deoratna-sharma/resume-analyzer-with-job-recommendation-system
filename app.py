from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, hashlib
from functools import wraps
import smtplib
import random
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = 'resumatch_2024_secret'
DB = 'resumatch.db'

# Email Configuration/ Credencials ---------------

GMAIL_ADDRESS = "shankarbaba720@gmail.com" # TODO: Replace with actual Gmail address
GMAIL_APP_PASSWORD = "dzfgpnweyunrgqqn" # TODO: Replace with 16-character App Password

# OTP Email Function -------------------
def send_otp_email(recipient_email, otp):
    msg = MIMEText(f"Your OTP for password reset is: {otp}\nThis OTP is valid for your current session.")
    msg['Subject'] = 'Password Reset OTP - ResuMatch'
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = recipient_email

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [recipient_email], msg.as_string())
        server.quit()
        print(f"OTP {otp} sent successfully to {recipient_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Even if email fails, we print it so the user can test locally
        print(f"--- FALLBACK OTP DISPLAY: {otp} ---")
        return False
    
# Database Connection ---------------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# password hashing -------------------
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# Database Initialization -------------------
def init_db():
    conn = get_db(); c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            department TEXT,
            location TEXT,
            type TEXT DEFAULT 'Full-time',
            description TEXT,
            required_skills TEXT,
            required_education TEXT,
            min_experience INTEGER DEFAULT 0,
            salary TEXT,
            openings INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            posted_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            full_name TEXT, phone TEXT, dob TEXT, gender TEXT,
            city TEXT, state TEXT,
            education TEXT, degree TEXT, specialization TEXT,
            institution TEXT, graduation_year TEXT, percentage TEXT,
            experience_years INTEGER DEFAULT 0,
            current_company TEXT, current_role TEXT, notice_period TEXT,
            technical_skills TEXT, soft_skills TEXT,
            certifications TEXT, projects TEXT,
            linkedin TEXT, portfolio TEXT, bio TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            match_score INTEGER DEFAULT 0,
            matched_skills TEXT,
            status TEXT DEFAULT 'Applied',
            hiring_notes TEXT,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(candidate_id, job_id)
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, subject TEXT, message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    # Seed users
    c.execute("INSERT OR IGNORE INTO users(name,email,password,role) VALUES(?,?,?,?)",
              ('Admin User','admin@company.com', hash_pw('admin123'), 'admin'))
    c.execute("INSERT OR IGNORE INTO users(name,email,password,role) VALUES(?,?,?,?)",
              ('HR Manager','hr@company.com', hash_pw('hr123'), 'hiring'))
    # Seed jobs
    jobs_data = []
    for j in jobs_data:
        c.execute('''INSERT OR IGNORE INTO jobs
            (title,department,location,type,description,required_skills,
             required_education,min_experience,salary,openings)
            VALUES(?,?,?,?,?,?,?,?,?,?)''', j)
    conn.commit(); conn.close()

# Matching Algorithm -------------------

def compute_match(candidate, job):
    skills = [s.strip().lower() for s in (candidate['technical_skills'] or '').split(',') if s.strip()]
    req    = [s.strip().lower() for s in (job['required_skills'] or '').split(',') if s.strip()]
    matched = [s for s in req if any(s in sk or sk in s for sk in skills)]
    skill_score = int((len(matched)/len(req))*60) if req else 0
    edu = (candidate['education'] or '').lower()
    edu_score = 20 if any(e.strip().lower() in edu for e in (job['required_education'] or '').split('/')) else 5
    exp = int(candidate['experience_years'] or 0)
    exp_score = 20 if exp >= job['min_experience'] else max(0, 10-(job['min_experience']-exp)*4)
    total = min(100, skill_score + edu_score + exp_score)
    return total, matched, req

# Role-based Access Control Decorator -------------------

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('user_role') not in roles:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ── PUBLIC ─────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    conn = get_db()
    jobs = conn.execute('SELECT * FROM jobs WHERE is_active=1 ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('home.html', jobs=jobs)

# Searchable Job Listings with Filters -------------------

@app.route('/jobs')
def all_jobs():
    conn = get_db()
    dept = request.args.get('dept','')
    loc  = request.args.get('loc','')
    q    = request.args.get('q','')
    query = 'SELECT * FROM jobs WHERE is_active=1'
    params = []
    if dept: query += ' AND department=?'; params.append(dept)
    if loc:  query += ' AND location=?';   params.append(loc)
    if q:    query += ' AND (title LIKE ? OR required_skills LIKE ?)'; params += [f'%{q}%',f'%{q}%']
    jobs = conn.execute(query + ' ORDER BY created_at DESC', params).fetchall()
    depts = conn.execute('SELECT DISTINCT department FROM jobs WHERE is_active=1').fetchall()
    locs  = conn.execute('SELECT DISTINCT location FROM jobs WHERE is_active=1').fetchall()
    conn.close()
    return render_template('all_jobs.html', jobs=jobs, depts=depts, locs=locs,
                           selected_dept=dept, selected_loc=loc, q=q)

# Contact Form Route -------------------
@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        conn = get_db()
        conn.execute('INSERT INTO contacts(name,email,subject,message) VALUES(?,?,?,?)',
            (request.form['name'], request.form['email'],
             request.form['subject'], request.form['message']))
        conn.commit(); conn.close()
        flash('Your message has been sent!', 'success')
    return render_template('contact.html')

# ── AUTH ──── Login -------------------
@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        r = session['user_role']
        return redirect(url_for('candidate_form' if r=='candidate' else
                                'hiring_dashboard' if r=='hiring' else 'admin_dashboard'))
    error = None
    if request.method == 'POST':
        role  = request.form['role']
        email = request.form['email']
        pw    = hash_pw(request.form['password'])
        conn  = get_db()
        user  = conn.execute(
            'SELECT * FROM users WHERE email=? AND password=? AND role=?',
            (email, pw, role)).fetchone()
        conn.close()
        if user:
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            if role == 'candidate':
                conn = get_db()
                cand = conn.execute('SELECT id FROM candidates WHERE user_id=?',(user['id'],)).fetchone()
                conn.close()
                return redirect(url_for('recommendations') if cand else url_for('candidate_form'))
            return redirect(url_for('hiring_dashboard') if role=='hiring' else url_for('admin_dashboard'))
        error = 'Invalid email, password, or role.'
    return render_template('login.html', error=error)

# Sign-up with OTP Verification -------------------

@app.route('/signup', methods=['GET','POST'])
def signup():
    error = None
    if request.method == 'POST':
        name  = request.form['name']
        email = request.form['email']
        pw    = hash_pw(request.form['password'])
        
        # Check if email exists
        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        
        if existing:
            error = 'Email already registered.'
        else:
            otp = str(random.randint(100000, 999999))
            session['signup_otp'] = otp
            session['signup_name'] = name
            session['signup_email'] = email
            session['signup_pw'] = pw
            
            send_otp_email(email, otp)
            flash("An OTP has been sent to your email to verify your registration.", "success")
            return redirect(url_for('verify_signup_otp'))
            
    return render_template('signup.html', error=error)

# OTP Verification for Sign-up -------------------

@app.route('/verify_signup_otp', methods=['GET', 'POST'])
def verify_signup_otp():
    if 'signup_otp' not in session or 'signup_email' not in session:
        flash("Session expired. Please try signing up again.", "error")
        return redirect(url_for('signup'))
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        if entered_otp == session['signup_otp']:
            # Create the account
            try:
                conn = get_db()
                conn.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',
                             (session['signup_name'], session['signup_email'], session['signup_pw'], 'candidate'))
                conn.commit(); conn.close()
                
                # Clear session variables
                session.pop('signup_otp', None)
                session.pop('signup_name', None)
                session.pop('signup_email', None)
                session.pop('signup_pw', None)
                
                flash('Account verified and created successfully! Please log in.', 'success')
                return redirect(url_for('login'))
            except:
                flash('An error occurred during registration. Please try again.', 'error')
                return redirect(url_for('signup'))
        else:
            flash("Invalid OTP.", "error")
            
    return render_template('verify_signup_otp.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Forgot Password with OTP Verification -------------------

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND role='candidate'", (email,)).fetchone()
        conn.close()
        
        if user:
            otp = str(random.randint(100000, 999999))
            session['reset_otp'] = otp
            session['reset_email'] = email
            
            # Send the email
            send_otp_email(email, otp)
            flash("An OTP has been sent to your email.", "success")
            return redirect(url_for('verify_otp'))
        else:
            flash("No candidate account found with that email address.", "error")
            
    return render_template('forgot_password.html')

# OTP Verification for Password Reset -------------------

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_otp' not in session or 'reset_email' not in session:
        flash("Session expired. Please request a new OTP.", "error")
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        if entered_otp == session['reset_otp']:
            # OTP is correct, save verified state
            session['otp_verified'] = True
            flash("OTP verified successfully.", "success")
            return redirect(url_for('reset_password'))
        else:
            flash("Invalid OTP.", "error")
            
    return render_template('verify_otp.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified') or 'reset_email' not in session:
        flash("Unauthorized access.", "error")
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            email = session['reset_email']
            hashed_pw = hash_pw(new_password)
            conn = get_db()
            conn.execute("UPDATE users SET password=? WHERE email=? AND role='candidate'", (hashed_pw, email))
            conn.commit()
            conn.close()
            
            # Clear session variables
            session.pop('reset_otp', None)
            session.pop('reset_email', None)
            session.pop('otp_verified', None)
            
            flash("Password reset successfully. You can now log in.", "success")
            return redirect(url_for('login'))
            
    return render_template('reset_password.html')

# ── CANDIDATE ──────
@app.route('/candidate/form', methods=['GET','POST'])
@require_role('candidate')
def candidate_form():
    conn = get_db()
    existing = conn.execute('SELECT * FROM candidates WHERE user_id=?',(session['user_id'],)).fetchone()
    conn.close()
    if request.method == 'POST':
        data = (
            request.form.get('full_name'), request.form.get('phone'),
            request.form.get('dob'), request.form.get('gender'),
            request.form.get('city'), request.form.get('state'),
            request.form.get('education'), request.form.get('degree'),
            request.form.get('specialization'), request.form.get('institution'),
            request.form.get('graduation_year'), request.form.get('percentage'),
            int(request.form.get('experience_years') or 0),
            request.form.get('current_company'), request.form.get('current_role'),
            request.form.get('notice_period'),
            request.form.get('technical_skills'), request.form.get('soft_skills'),
            request.form.get('certifications'), request.form.get('projects'),
            request.form.get('linkedin'), request.form.get('portfolio'),
            request.form.get('bio'), session['user_id']
        )
        conn = get_db()
        if existing:
            conn.execute('''UPDATE candidates SET full_name=?,phone=?,dob=?,gender=?,
                city=?,state=?,education=?,degree=?,specialization=?,institution=?,
                graduation_year=?,percentage=?,experience_years=?,current_company=?,
                current_role=?,notice_period=?,technical_skills=?,soft_skills=?,
                certifications=?,projects=?,linkedin=?,portfolio=?,bio=?,
                updated_at=CURRENT_TIMESTAMP WHERE user_id=?''', data)
        else:
            conn.execute('''INSERT INTO candidates(full_name,phone,dob,gender,city,state,
                education,degree,specialization,institution,graduation_year,percentage,
                experience_years,current_company,current_role,notice_period,technical_skills,
                soft_skills,certifications,projects,linkedin,portfolio,bio,user_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', data)
        conn.commit(); conn.close()
        return redirect(url_for('recommendations'))
    return render_template('candidate_form.html', candidate=existing)

# Job Recommendations and Application -------------------

@app.route('/candidate/recommendations')
@require_role('candidate')
def recommendations():
    conn = get_db()
    cand = conn.execute('SELECT * FROM candidates WHERE user_id=?',(session['user_id'],)).fetchone()
    if not cand:
        conn.close()
        return redirect(url_for('candidate_form'))
    jobs = conn.execute('SELECT * FROM jobs WHERE is_active=1').fetchall()
    applied_ids = [r['job_id'] for r in conn.execute(
        'SELECT job_id FROM applications WHERE candidate_id=?',(cand['id'],)).fetchall()]
    conn.close()
    results = []
    for job in jobs:
        score, matched, req = compute_match(cand, job)
        results.append({**dict(job), 'score': score,
                        'matched_skills': matched, 'required_list': req})
    results.sort(key=lambda x: x['score'], reverse=True)
    return render_template('recommendations.html', jobs=results,
                           candidate=cand, applied_ids=applied_ids)

@app.route('/candidate/apply/<int:job_id>', methods=['POST'])
@require_role('candidate')
def apply_job(job_id):
    conn = get_db()
    cand = conn.execute('SELECT * FROM candidates WHERE user_id=?',(session['user_id'],)).fetchone()
    job  = conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if cand and job:
        score, matched, _ = compute_match(cand, job)
        try:
            conn.execute('''INSERT INTO applications(candidate_id,job_id,match_score,matched_skills)
                VALUES(?,?,?,?)''', (cand['id'], job_id, score, ','.join(matched)))
            conn.commit()
        except: pass
    conn.close()
    return redirect(url_for('recommendations'))

# ── HIRING TEAM ──
@app.route('/hiring')
@require_role('hiring')
def hiring_dashboard():
    conn = get_db()
    apps = conn.execute('''
        SELECT a.*, c.full_name, c.phone, c.education, c.degree, c.experience_years,
               c.technical_skills, c.city, c.notice_period, c.linkedin,
               u.email as candidate_email,
               j.title as job_title, j.department
        FROM applications a
        JOIN candidates c ON a.candidate_id=c.id
        JOIN users u ON c.user_id=u.id
        JOIN jobs j ON a.job_id=j.id
        ORDER BY a.applied_at DESC
    ''').fetchall()
    jobs = conn.execute('SELECT * FROM jobs WHERE is_active=1 ORDER BY title').fetchall()
    stats = {
        'total': conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
        'new': conn.execute("SELECT COUNT(*) FROM applications WHERE status='Applied'").fetchone()[0],
        'shortlisted': conn.execute("SELECT COUNT(*) FROM applications WHERE status='Shortlisted'").fetchone()[0],
        'interview': conn.execute("SELECT COUNT(*) FROM applications WHERE status='Interview'").fetchone()[0],
    }
    conn.close()
    return render_template('hiring.html', applications=apps, jobs=jobs, stats=stats)

# Update Application Status and Auto-Manage Job Openings -------------------

@app.route('/hiring/update', methods=['POST'])
@require_role('hiring')
def hiring_update():
    conn = get_db()
    new_status = request.form['status']
    app_id = request.form['app_id']
    notes = request.form.get('notes', '')
    
    # Check old status to see if we're transitioning to or from 'Offered'
    app_record = conn.execute('SELECT * FROM applications WHERE id=?', (app_id,)).fetchone()
    if app_record:
        old_status = app_record['status']
        job_id = app_record['job_id']
        
        # Update the application status
        conn.execute('''UPDATE applications SET status=?, hiring_notes=?,
            updated_at=CURRENT_TIMESTAMP WHERE id=?''',
            (new_status, notes, app_id))
        
        # If changing to Offered, reduce the job openings
        if new_status == 'Offered' and old_status != 'Offered':
            conn.execute('UPDATE jobs SET openings = MAX(0, openings - 1) WHERE id=?', (job_id,))
            
            # Auto-close the job role if no openings are left
            job = conn.execute('SELECT openings FROM jobs WHERE id=?', (job_id,)).fetchone()
            if job and job['openings'] == 0:
                conn.execute('UPDATE jobs SET is_active=0 WHERE id=?', (job_id,))
                
        # If changing away from Offered, restore the job opening
        elif new_status != 'Offered' and old_status == 'Offered':
            conn.execute('UPDATE jobs SET openings = openings + 1 WHERE id=?', (job_id,))
            conn.execute('UPDATE jobs SET is_active=1 WHERE id=?', (job_id,))
            
    conn.commit(); conn.close()
    return redirect(url_for('hiring_dashboard'))

# Add New Job Role with Limit Check -------------------

@app.route('/hiring/add_job', methods=['POST'])
@require_role('hiring')
def hiring_add_job():
    conn = get_db()
    
    total_roles = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
    if total_roles >= 15:
        flash('Cannot post job. Maximum limit of 15 job roles reached.', 'error')
        conn.close()
        return redirect(url_for('hiring_dashboard'))
        
    conn.execute('''INSERT INTO jobs(title,department,location,type,description,
        required_skills,required_education,min_experience,salary,openings,posted_by)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        (request.form['title'], request.form['department'], request.form['location'],
         request.form['type'], request.form['description'], request.form['required_skills'],
         request.form['required_education'], int(request.form.get('min_experience',0)),
         request.form['salary'], int(request.form.get('openings',1)), session['user_id']))
    conn.commit(); conn.close()
    return redirect(url_for('hiring_dashboard'))

@app.route('/hiring/toggle_job/<int:job_id>')
@require_role('hiring')
def toggle_job(job_id):
    conn = get_db()
    conn.execute('UPDATE jobs SET is_active=1-is_active WHERE id=?',(job_id,))
    conn.commit(); conn.close()
    return redirect(url_for('hiring_dashboard'))

# ── ADMIN DASHBOARD ──-------------------------
@app.route('/admin')
@require_role('admin')
def admin_dashboard():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    jobs  = conn.execute("SELECT j.*, u.name as poster FROM jobs j LEFT JOIN users u ON j.posted_by=u.id ORDER BY j.created_at DESC").fetchall()
    apps  = conn.execute('''SELECT a.*, c.full_name, u.email, j.title as job_title
        FROM applications a JOIN candidates c ON a.candidate_id=c.id
        JOIN users u ON c.user_id=u.id JOIN jobs j ON a.job_id=j.id
        ORDER BY a.applied_at DESC''').fetchall()
    contacts = conn.execute('SELECT * FROM contacts ORDER BY created_at DESC').fetchall()
    stats = {
        'users': conn.execute("SELECT COUNT(*) FROM users WHERE role='candidate'").fetchone()[0],
        'jobs': conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
        'active_jobs': conn.execute('SELECT COUNT(*) FROM jobs WHERE is_active=1').fetchone()[0],
        'apps': conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
    }
    conn.close()
    return render_template('admin.html', users=users, jobs=jobs,
                           applications=apps, contacts=contacts, stats=stats)

# Admin Delete User (Candidates Only) -------------------

@app.route('/admin/delete_user/<int:uid>')
@require_role('admin')
def delete_user(uid):
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id=? AND role="candidate"',(uid,))
    conn.commit(); conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_job/<int:jid>')
@require_role('admin')
def admin_toggle_job(jid):
    conn = get_db()
    conn.execute('UPDATE jobs SET is_active=1-is_active WHERE id=?',(jid,))
    conn.commit(); conn.close()
    return redirect(url_for('admin_dashboard'))

# Admin Add User (Candidates Only) -------------------
@app.route('/admin/add_user', methods=['POST'])
@require_role('admin')
def admin_add_user():
    try:
        conn = get_db()
        conn.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',
            (request.form['name'], request.form['email'],
             hash_pw(request.form['password']), request.form['role']))
        conn.commit(); conn.close()
    except: pass
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)

