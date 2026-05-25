import streamlit as st
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import re
import json
from pathlib import Path

# ==================== CONFIGURATION ====================
RECIPIENT_EMAIL = "sbrightaboh@gmail.com"

st.set_page_config(
    page_title="EPA Consignment Inspection Checklist",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for fullscreen camera and better layout
st.markdown("""
    <style>
    .main-header { background-color: #2E7D32; padding: 1rem; border-radius: 10px; color: white; text-align: center; }
    .section-header { background-color: #388E3C; padding: 0.5rem; border-radius: 5px; color: white; margin-top: 1rem; }
    .sub-section { background-color: #F5F5F5; padding: 1rem; border-radius: 5px; margin-bottom: 1rem; }
    .success-box { background-color: #D4EDDA; padding: 1rem; border-radius: 5px; border-left: 5px solid #28A745; }
    .error-box { background-color: #F8D7DA; padding: 1rem; border-radius: 5px; border-left: 5px solid #DC3545; }
    .photo-status { background-color: #E8F5E9; padding: 0.5rem; border-radius: 5px; margin: 0.5rem 0; }
    .current-step { background-color: #FFF3E0; padding: 1rem; border-radius: 5px; border-left: 5px solid #FF9800; margin: 1rem 0; }
    .info-box { background-color: #E3F2FD; padding: 1rem; border-radius: 5px; border-left: 5px solid #2196F3; margin: 1rem 0; }
    .camera-buttons { display: flex; gap: 10px; margin: 10px 0; flex-wrap: wrap; }
    .camera-btn { flex: 1; min-width: 120px; }
    
    /* Fullscreen camera styling */
    .stCamera input {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        z-index: 9999 !important;
        object-fit: cover !important;
    }
    
    /* Camera container fullscreen */
    .stCamera {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 10000 !important;
        background: black !important;
    }
    
    /* Make camera preview fullscreen */
    .stCamera video {
        width: 100% !important;
        height: 100% !important;
        object-fit: cover !important;
    }
    
    /* Camera button styling for better visibility */
    .stCamera button {
        z-index: 10001 !important;
        position: fixed !important;
        bottom: 30px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
    }
    
    @media (min-width: 768px) and (max-width: 1024px) {
        .camera-buttons { gap: 15px; }
        .stButton button { font-size: 1.1rem; padding: 0.75rem; }
    }
    </style>
""", unsafe_allow_html=True)

# JavaScript for fullscreen camera
st.markdown("""
    <script>
    // Function to request fullscreen when camera is active
    function requestFullscreen(element) {
        if (element.requestFullscreen) {
            element.requestFullscreen();
        } else if (element.webkitRequestFullscreen) {
            element.webkitRequestFullscreen();
        } else if (element.msRequestFullscreen) {
            element.msRequestFullscreen();
        }
    }
    
    // Listen for camera activation
    const observer = new MutationObserver(function(mutations) {
        const cameraElement = document.querySelector('.stCamera video');
        if (cameraElement && !cameraElement.hasAttribute('data-fullscreen-enabled')) {
            cameraElement.setAttribute('data-fullscreen-enabled', 'true');
            // Request fullscreen when camera appears
            requestFullscreen(document.documentElement);
        }
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
    </script>
""", unsafe_allow_html=True)

# ==================== HELPER FUNCTIONS ====================

def validate_date(date_value, field_name):
    today = date.today()
    if date_value < today:
        return False, f"❌ {field_name} cannot be in the past"
    elif date_value > today:
        return False, f"❌ {field_name} cannot be in the future"
    return True, f"✓ {field_name} is valid"

def validate_amount_words(amount_words):
    if not amount_words or not amount_words.strip():
        return False, "Amount in words is required"
    if any(char.isdigit() for char in amount_words):
        return False, "❌ Numbers are not allowed! Please use words only"
    return True, "✓ Valid text format"

def validate_email(email):
    if not email:
        return False, "Email is required"
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        return True, "✓ Valid email format"
    return False, "❌ Invalid email address"

def save_inspection_report(data, photos, email_sent=False):
    try:
        report_dir = Path("inspection_reports")
        report_dir.mkdir(exist_ok=True)
        
        data['email_sent'] = email_sent
        data['email_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if email_sent else None
        
        json_path = report_dir / f"{data['inspection_id']}.json"
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        if email_sent:
            photos_dir = report_dir / data['inspection_id']
            photos_dir.mkdir(exist_ok=True)
            
            for photo_name, photo_data in photos.items():
                if photo_data:
                    photo_data.seek(0)
                    photo_path = photos_dir / f"{photo_name}.jpg"
                    with open(photo_path, 'wb') as f:
                        f.write(photo_data.read())
        
        return True, "Report saved"
    except Exception as e:
        return False, f"Failed to save: {str(e)}"

def load_inspection_report(inspection_id):
    try:
        report_dir = Path("inspection_reports")
        json_path = report_dir / f"{inspection_id}.json"
        
        if not json_path.exists():
            return None
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        if not data.get('email_sent', False):
            return None
        
        photos = {}
        photos_dir = report_dir / inspection_id
        if photos_dir.exists():
            for photo_file in photos_dir.glob("*.jpg"):
                photo_name = photo_file.stem
                with open(photo_file, 'rb') as f:
                    photos[photo_name] = f.read()
        
        return {"data": data, "photos": photos}
    except Exception as e:
        st.error(f"Error loading report: {str(e)}")
        return None

def get_recent_reports():
    try:
        report_dir = Path("inspection_reports")
        if not report_dir.exists():
            return []
        
        reports = []
        for json_file in report_dir.glob("EPA-*.json"):
            with open(json_file, 'r') as f:
                data = json.load(f)
                if data.get('email_sent', False):
                    reports.append({
                        "id": data['inspection_id'],
                        "timestamp": data['timestamp'],
                        "consignment": data.get('consignment', 'N/A'),
                        "agent": data.get('agent_name', 'N/A'),
                        "email_timestamp": data.get('email_timestamp', 'N/A')
                    })
        
        reports.sort(key=lambda x: x['timestamp'], reverse=True)
        return reports
    except Exception as e:
        return []

def send_email_report(sender_email, data, photos):
    try:
        SMTP_SERVER = st.secrets["SMTP_SERVER"]
        SMTP_PORT = st.secrets["SMTP_PORT"]
        SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
        SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
        
        subject = f"EPA Inspection Report - {data['inspection_id']}"
        
        html_body = f"""
        <html>
        <head><style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background-color: #2E7D32; color: white; padding: 10px; }}
            .section {{ margin: 20px 0; border: 1px solid #ddd; padding: 10px; }}
            .field {{ margin: 5px 0; }}
            .label {{ font-weight: bold; display: inline-block; width: 200px; }}
        </style></head>
        <body>
            <div class="header"><h2>ENVIRONMENTAL PROTECTION AUTHORITY</h2><h3>CONSIGNMENT INSPECTION REPORT</h3></div>
            <p><strong>Report submitted by:</strong> {sender_email}</p>
            <p><strong>Submission time:</strong> {data['timestamp']}</p>
            
            <div class="section">
                <h3>PART I — PHYSICAL INSPECTION</h3>
                <div class="field"><span class="label">Inspection ID:</span> {data['inspection_id']}</div>
                <div class="field"><span class="label">Consignment:</span> {data['consignment']}</div>
                <div class="field"><span class="label">Agent/Consignee:</span> {data['agent_name']}</div>
                <div class="field"><span class="label">Contact:</span> {data['contact']}</div>
                <div class="field"><span class="label">Container Numbers:</span> {data['container_numbers']}</div>
                <div class="field"><span class="label">Bill of Lading:</span> {data['bill_of_lading']}</div>
                <div class="field"><span class="label">Bill of Entry:</span> {data['bill_of_entry']}</div>
                <div class="field"><span class="label">Engine/Items:</span> {data['engine_items']}</div>
                <div class="field"><span class="label">Horsepower:</span> {data['hp_rating']}</div>
                <div class="field"><span class="label">Associated Parts:</span> {data['associated_parts']}</div>
            </div>
            
            <div class="section">
                <h3>PART II — BILLING</h3>
                <div class="field"><span class="label">Proponent:</span> {data['proponent_name']}</div>
                <div class="field"><span class="label">Nature:</span> {data['nature_undertaking']}</div>
                <div class="field"><span class="label">Location:</span> {data['location']}</div>
                <div class="field"><span class="label">Address:</span> {data['address']}</div>
                <div class="field"><span class="label">Contact Person:</span> {data['contact_person']}</div>
                <div class="field"><span class="label">Telephone:</span> {data['telephone']}</div>
                <div class="field"><span class="label">Containers:</span> {data['num_containers']}</div>
                <div class="field"><span class="label">Consignment Type:</span> {data['consignment_type']}</div>
                <div class="field"><span class="label">Clearance Fee:</span> {data['clearance_fee']}</div>
                <div class="field"><span class="label">Penalty:</span> {data['penalty']}</div>
                <div class="field"><span class="label">Amount:</span> GHS {data['amount_figures']:,.2f}</div>
                <div class="field"><span class="label">Amount in Words:</span> {data['amount_words']}</div>
            </div>
            
            <div class="section">
                <h3>SIGNATURES</h3>
                <div class="field"><span class="label">Prepared by:</span> {data['prepared_by']}</div>
                <div class="field"><span class="label">Signature:</span> {data['prepared_signature']}</div>
                <div class="field"><span class="label">Date:</span> {data['prepared_date']}</div>
                <div class="field"><span class="label">Reviewed by:</span> {data['reviewed_by']}</div>
                <div class="field"><span class="label">Signature:</span> {data['reviewed_signature']}</div>
                <div class="field"><span class="label">Date:</span> {data['reviewed_date']}</div>
            </div>
            
            <p><strong>Photos attached:</strong> Front, Left, Right, Back views</p>
            <p><em>This is an automated report from EPA Inspection System</em></p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        for photo_name, photo_data in photos.items():
            if photo_data:
                photo_data.seek(0)
                attachment = MIMEBase('application', 'octet-stream')
                attachment.set_payload(photo_data.read())
                encoders.encode_base64(attachment)
                attachment.add_header('Content-Disposition', f'attachment; filename={photo_name}_{data["inspection_id"]}.jpg')
                msg.attach(attachment)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        if sender_email and sender_email != RECIPIENT_EMAIL:
            try:
                msg_copy = MIMEMultipart()
                msg_copy['From'] = SENDER_EMAIL
                msg_copy['To'] = sender_email
                msg_copy['Subject'] = f"Copy: {subject}"
                msg_copy.attach(MIMEText(html_body, 'html'))
                for photo_name, photo_data in photos.items():
                    if photo_data:
                        photo_data.seek(0)
                        attachment = MIMEBase('application', 'octet-stream')
                        attachment.set_payload(photo_data.read())
                        encoders.encode_base64(attachment)
                        attachment.add_header('Content-Disposition', f'attachment; filename={photo_name}_{data["inspection_id"]}.jpg')
                        msg_copy.attach(attachment)
                server.send_message(msg_copy)
            except:
                pass
        
        return True, f"Report sent to {RECIPIENT_EMAIL}"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

# ==================== INITIALIZE SESSION STATE ====================

if 'step' not in st.session_state:
    st.session_state.step = 'photos'

if 'active_camera' not in st.session_state:
    st.session_state.active_camera = None

if 'photos' not in st.session_state:
    st.session_state.photos = {'front': None, 'left': None, 'right': None, 'back': None}

if 'form_data' not in st.session_state:
    st.session_state.form_data = {}

if 'view_mode' not in st.session_state:
    st.session_state.view_mode = None

if 'view_report_data' not in st.session_state:
    st.session_state.view_report_data = None

if 'show_success' not in st.session_state:
    st.session_state.show_success = False

if 'last_inspection_id' not in st.session_state:
    st.session_state.last_inspection_id = None

if 'email_sent_status' not in st.session_state:
    st.session_state.email_sent_status = False

# ==================== SIDEBAR ====================
st.sidebar.markdown("## 📋 Navigation")
st.sidebar.markdown("---")

if st.sidebar.button("📸 New Inspection", use_container_width=True):
    st.session_state.step = 'photos'
    st.session_state.active_camera = None
    st.session_state.photos = {'front': None, 'left': None, 'right': None, 'back': None}
    st.session_state.form_data = {}
    st.session_state.show_success = False
    st.session_state.view_mode = None
    st.session_state.email_sent_status = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("## 📊 Successfully Emailed Reports")
st.sidebar.caption("Showing only reports that were sent via email")

recent_reports = get_recent_reports()
if recent_reports:
    for report in recent_reports[:10]:
        button_label = f"📧 {report['id']}\n{report['timestamp'][:10]}"
        if st.sidebar.button(button_label, key=f"view_{report['id']}", use_container_width=True):
            report_data = load_inspection_report(report['id'])
            if report_data:
                st.session_state.view_mode = 'view'
                st.session_state.view_report_data = report_data
                st.session_state.step = 'view'
                st.rerun()
    
    st.sidebar.success(f"✅ {len(recent_reports)} reports emailed successfully")
else:
    st.sidebar.info("No reports have been successfully emailed yet")

st.sidebar.markdown("---")
st.sidebar.caption(f"EPA Ghana System\n{datetime.now().year}")

# ==================== HEADER ====================
st.markdown('<div class="main-header"><h1> ENVIRONMENTAL PROTECTION AUTHORITY</h1><h2>STANDARD OPERATING PROCEDURE</h2><h3>CONSIGNMENT INSPECTION CHECKLIST</h3></div>', unsafe_allow_html=True)
st.markdown("---")

today = date.today()
st.info(f"📅 Today's Date: **{today.strftime('%A, %B %d, %Y')}**")



# ==================== VIEW MODE ====================
if st.session_state.step == 'view' and st.session_state.view_report_data:
    report = st.session_state.view_report_data['data']
    photos = st.session_state.view_report_data['photos']
    
    st.markdown('<div class="section-header"><h2>📄 VIEW INSPECTION REPORT (Read Only)</h2></div>', unsafe_allow_html=True)
    
    if st.button("← Back to New Inspection", use_container_width=True):
        st.session_state.view_mode = None
        st.session_state.view_report_data = None
        st.session_state.step = 'photos'
        st.rerun()
    
    st.markdown(f"""
    <div class="success-box">
        <p><strong>Inspection ID:</strong> {report['inspection_id']}</p>
        <p><strong>Date/Time:</strong> {report['timestamp']}</p>
        <p><strong>Email Sent:</strong> ✅ Yes at {report.get('email_timestamp', 'N/A')}</p>
        <p><strong>Status:</strong> 🔒 View Only Mode</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📸 Inspection Photos")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if 'front' in photos:
            st.image(photos['front'], caption="Front View", width=150)
    with col2:
        if 'left' in photos:
            st.image(photos['left'], caption="Left View", width=150)
    with col3:
        if 'right' in photos:
            st.image(photos['right'], caption="Right View", width=150)
    with col4:
        if 'back' in photos:
            st.image(photos['back'], caption="Back View", width=150)
    
    st.markdown("---")
    
    st.markdown("### PART I — PHYSICAL INSPECTION")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**1. Consignment:** {report['consignment']}")
        st.markdown(f"**2. Agent/Consignee:** {report['agent_name']}")
        st.markdown(f"**3. Contact:** {report['contact']}")
        st.markdown(f"**4. Container Numbers:** {report['container_numbers']}")
        st.markdown(f"**5. Bill of Lading:** {report['bill_of_lading']}")
        st.markdown(f"**6. Bill of Entry:** {report['bill_of_entry']}")
    with col2:
        st.markdown(f"**7. Engine/Items:** {report['engine_items']}")
        st.markdown(f"**8. Horsepower:** {report['hp_rating']}")
        st.markdown(f"**9. Associated Parts:** {report['associated_parts']}")
    
    st.markdown("---")
    st.markdown("### PART II — BILLING")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Name of Proponent:** {report['proponent_name']}")
        st.markdown(f"**Nature of Undertaking:** {report['nature_undertaking']}")
        st.markdown(f"**Location:** {report['location']}")
        st.markdown(f"**Address:** {report['address']}")
    with col2:
        st.markdown(f"**Contact Person:** {report['contact_person']}")
        st.markdown(f"**Telephone:** {report['telephone']}")
        st.markdown(f"**Number of Containers:** {report['num_containers']}")
        st.markdown(f"**Consignment Type:** {report['consignment_type']}")
    
    st.markdown("### Fees")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Clearance Fee:** {report['clearance_fee']}")
        st.markdown(f"**Penalty:** {report['penalty']}")
    with col2:
        st.markdown(f"**Amount (GHC):** GHS {report['amount_figures']:,.2f}")
        st.markdown(f"**Amount in Words:** {report['amount_words']}")
    
    st.markdown("---")
    st.markdown("### SIGNATURES")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Prepared by:** {report['prepared_by']}")
        st.markdown(f"**Signature:** {report['prepared_signature']}")
        st.markdown(f"**Date:** {report['prepared_date']}")
    with col2:
        st.markdown(f"**Reviewed by:** {report['reviewed_by']}")
        st.markdown(f"**Signature:** {report['reviewed_signature']}")
        st.markdown(f"**Date:** {report['reviewed_date']}")
    
    st.stop()

# ==================== SUCCESS SCREEN ====================
if st.session_state.show_success:
    if st.session_state.email_sent_status:
        st.markdown(f"""
        <div class="success-box">
            <h3>✅ INSPECTION REPORT SENT SUCCESSFULLY!</h3>
            <p><strong>Inspection ID:</strong> {st.session_state.last_inspection_id}</p>
            <p><strong>Email sent to:</strong> {RECIPIENT_EMAIL}</p>
            <p><strong>Time:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p><strong>Status:</strong> Report saved and email confirmed</p>
        </div>
        """, unsafe_allow_html=True)
        st.balloons()
    else:
        st.markdown(f"""
        <div class="error-box">
            <h3>⚠️ EMAIL FAILED - REPORT NOT SAVED</h3>
            <p><strong>Inspection ID:</strong> {st.session_state.last_inspection_id}</p>
            <p><strong>Status:</strong> Email could not be sent</p>
            <p>Please check your email configuration and try again.</p>
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 START NEW INSPECTION", type="primary", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key not in ['view_mode', 'view_report_data']:
                    del st.session_state[key]
            st.rerun()
    with col2:
        if st.button("📄 VIEW EMAILED REPORTS", use_container_width=True):
            st.session_state.show_success = False
            st.rerun()
    
    st.stop()

# ==================== PHOTO CAPTURE WITH BUTTONS ====================

# ==================== PHOTO CAPTURE WITH BUTTONS ====================
if st.session_state.step == 'photos':
    st.markdown('<div class="section-header"><h2>📸 STEP 1: CAPTURE PHOTOS</h2></div>', unsafe_allow_html=True)
    
    # Progress status at the top
    st.markdown('<div class="photo-status">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.session_state.photos['front']:
            st.success("✅ Front View")
        else:
            st.warning("⏳ Front View")
    with col2:
        if st.session_state.photos['left']:
            st.success("✅ Left View")
        else:
            st.warning("⏳ Left View")
    with col3:
        if st.session_state.photos['right']:
            st.success("✅ Right View")
        else:
            st.warning("⏳ Right View")
    with col4:
        if st.session_state.photos['back']:
            st.success("✅ Back View")
        else:
            st.warning("⏳ Back View")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Capture buttons section
    st.markdown("### Tap a button below to capture each view:")
    st.caption("Camera will open in FULL SCREEN mode for better visibility")
    
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    
    with col_btn1:
        if not st.session_state.photos['front']:
            if st.button("📷 Capture FRONT View", key="btn_front", use_container_width=True):
                st.session_state.active_camera = 'front'
                st.rerun()
        else:
            if st.button("🔄 Retake FRONT View", key="retake_front_btn", use_container_width=True):
                st.session_state.photos['front'] = None
                st.session_state.active_camera = 'front'
                st.rerun()
    
    with col_btn2:
        if not st.session_state.photos['left']:
            if st.button("📷 Capture LEFT View", key="btn_left", use_container_width=True):
                st.session_state.active_camera = 'left'
                st.rerun()
        else:
            if st.button("🔄 Retake LEFT View", key="retake_left_btn", use_container_width=True):
                st.session_state.photos['left'] = None
                st.session_state.active_camera = 'left'
                st.rerun()
    
    with col_btn3:
        if not st.session_state.photos['right']:
            if st.button("📷 Capture RIGHT View", key="btn_right", use_container_width=True):
                st.session_state.active_camera = 'right'
                st.rerun()
        else:
            if st.button("🔄 Retake RIGHT View", key="retake_right_btn", use_container_width=True):
                st.session_state.photos['right'] = None
                st.session_state.active_camera = 'right'
                st.rerun()
    
    with col_btn4:
        if not st.session_state.photos['back']:
            if st.button("📷 Capture BACK View", key="btn_back", use_container_width=True):
                st.session_state.active_camera = 'back'
                st.rerun()
        else:
            if st.button("🔄 Retake BACK View", key="retake_back_btn", use_container_width=True):
                st.session_state.photos['back'] = None
                st.session_state.active_camera = 'back'
                st.rerun()
    
    st.markdown("---")
    
    # Camera input section - appears BETWEEN buttons and captured photos preview
    if st.session_state.active_camera:
        view_names = {
            'front': 'FRONT',
            'left': 'LEFT',
            'right': 'RIGHT',
            'back': 'BACK'
        }
        
        view_tips = {
            'front': "Stand directly in front of the equipment",
            'left': "Stand on the LEFT side of the equipment",
            'right': "Stand on the RIGHT side of the equipment",
            'back': "Stand directly behind the equipment"
        }
        
        current_view = st.session_state.active_camera
        st.markdown(f"""
        <div class="current-step">
            <h3>📷 Capturing {view_names[current_view]} View</h3>
            <p><strong>Tip:</strong> {view_tips[current_view]}</p>
            <p>💡 <strong>Camera is in FULL SCREEN mode</strong> - The camera will take up your entire screen for better visibility</p>
            <p>💡 <strong>To switch cameras:</strong> Look for the camera switch icon 🔄 (usually at the bottom or top corner)</p>
            <p>💡 <strong>To take photo:</strong> Tap the capture button at the bottom of the screen</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Camera input - this will open in full screen
        camera_photo = st.camera_input(
            f"Take photo of the {view_names[current_view]} view",
            key=f"camera_{current_view}"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.active_camera = None
                st.rerun()
        
        if camera_photo:
            st.session_state.photos[current_view] = camera_photo
            st.session_state.active_camera = None
            st.success(f"✅ {view_names[current_view]} view captured successfully!")
            st.rerun()
        
        st.markdown("---")
    
    # Captured photos preview (appears AFTER camera, or directly after buttons if no active camera)
    st.markdown("### 📷 Captured Photos So Far:")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.session_state.photos['front']:
            st.image(st.session_state.photos['front'], caption="✓ Front", width=120)
        else:
            st.markdown("📷 Front: Not captured")
    with col2:
        if st.session_state.photos['left']:
            st.image(st.session_state.photos['left'], caption="✓ Left", width=120)
        else:
            st.markdown("📷 Left: Not captured")
    with col3:
        if st.session_state.photos['right']:
            st.image(st.session_state.photos['right'], caption="✓ Right", width=120)
        else:
            st.markdown("📷 Right: Not captured")
    with col4:
        if st.session_state.photos['back']:
            st.image(st.session_state.photos['back'], caption="✓ Back", width=120)
        else:
            st.markdown("📷 Back: Not captured")
    
    st.markdown("---")
    
    # Continue button when all photos are captured
    if all(st.session_state.photos.values()):
        st.success("### ✅ All 4 photos captured successfully!")
        
        if st.button("📝 Continue to Inspection Details →", type="primary", use_container_width=True):
            st.session_state.step = 'details'
            st.rerun()

# ==================== INSPECTION DETAILS FORM ====================
if st.session_state.step == 'details':
    st.markdown('<div class="section-header"><h2>📋 STEP 2: COMPLETE INSPECTION DETAILS</h2></div>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-box">
        <p>📧 <strong>Report will be sent to:</strong> {RECIPIENT_EMAIL}</p>
        <p>💡 You will receive a confirmation copy at your email address.</p>
        <p>⚠️ <strong>IMPORTANT:</strong> Reports are ONLY saved if email is sent successfully!</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("inspection_form"):
        st.markdown("### PART I — PHYSICAL INSPECTION (At the Terminal)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            consignment = st.text_input("1. Consignment *", key="consignment")
            agent_name = st.text_input("2. Name of Agent/Consignee *", key="agent")
            contact = st.text_input("3. Contact", key="contact")
            container_numbers = st.text_input("4. Container Number(s) *", key="container")
            bill_of_lading = st.text_input("5. Bill of Lading Number(s) *", key="bol")
            bill_of_entry = st.text_input("6. Bill of Entry Number(s)", key="boe")
        
        with col2:
            engine_items = st.text_area("7. Type of Engine/Items/Machinery *", key="engine", height=100)
            
            st.markdown("8. Horsepower (HP) rating:")
            hp_rating = st.radio("Select HP rating", ["1 – 11", "12 – 25", "Above 25"], horizontal=True, key="hp")
            
            associated_parts = st.text_area("9. Other associated parts and components", key="parts", height=80)
        
        st.markdown("---")
        
        st.markdown("### PART II — BILLING")
        st.markdown("#### TEMA PORT OFFICE BILLING FORM")
        
        col3, col4 = st.columns(2)
        
        with col3:
            proponent_name = st.text_input("Name of Proponent *", key="proponent")
            nature_undertaking = st.text_input("Nature of Undertaking", key="nature")
            location = st.text_input("Location", key="location")
            address = st.text_input("Address", key="address")
        
        with col4:
            contact_person = st.text_input("Name of Contact Person", key="contact_person")
            telephone = st.text_input("Telephone", key="telephone")
            num_containers = st.number_input("Number of containers", min_value=1, value=1, key="num_containers")
            
            st.markdown("Consignment Type:")
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                is_mining = st.checkbox("Mining", key="mining")
            with col_t2:
                is_agricultural = st.checkbox("Agricultural", key="agricultural")
            with col_t3:
                other_type = st.text_input("Others:", key="other")
        
        st.markdown("### Fees")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            clearance_fee = st.checkbox("Clearance fee", key="clearance")
        with col_f2:
            penalty = st.checkbox("Penalty", key="penalty")
        
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            amount_figures = st.number_input("Amount in Figures (GHC) *", min_value=0.0, step=0.01, key="amount_figures")
        with col_a2:
            amount_words = st.text_input("Amount in Words *", 
                                        placeholder="e.g., One Thousand Ghana Cedis",
                                        key="amount_words")
            if amount_words and any(char.isdigit() for char in amount_words):
                st.error("❌ Numbers not allowed! Please use words only")
        
        st.markdown("---")
        
        st.markdown("### SIGNATURES")
        st.markdown(f"⚠️ **Date must be TODAY: {today.strftime('%Y-%m-%d')}**")
        
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            prepared_by = st.text_input("Prepared by *", key="prepared_by")
            prepared_signature = st.text_input("Signature *", key="prepared_sig")
            prepared_date = st.date_input("Date *", value=today, key="prepared_date")
            if prepared_date and prepared_date != today:
                st.error(f"Date must be today ({today})")
        
        with col_s2:
            reviewed_by = st.text_input("Bill reviewed by *", key="reviewed_by")
            reviewed_signature = st.text_input("Signature *", key="reviewed_sig")
            reviewed_date = st.date_input("Date *", value=today, key="reviewed_date")
            if reviewed_date and reviewed_date != today:
                st.error(f"Date must be today ({today})")
        
        st.markdown("---")
        
        st.markdown("### 📧 YOUR CONTACT INFORMATION")
        st.caption("We'll send a confirmation copy to your email address")
        
        sender_email = st.text_input("Your Email Address *", placeholder="you@example.com", key="sender_email")
        if sender_email:
            if validate_email(sender_email)[0]:
                st.success("✓ Valid email format")
            else:
                st.error("❌ Invalid email address")
        
        submitted = st.form_submit_button("✅ SUBMIT & SEND INSPECTION REPORT", type="primary", use_container_width=True)
        
        if submitted:
            errors = []
            
            if not consignment:
                errors.append("Consignment is required")
            if not agent_name:
                errors.append("Agent/Consignee name is required")
            if not container_numbers:
                errors.append("Container Number(s) is required")
            if not bill_of_lading:
                errors.append("Bill of Lading Number(s) is required")
            if not engine_items:
                errors.append("Type of Engine/Items is required")
            if not proponent_name:
                errors.append("Name of Proponent is required")
            if amount_figures <= 0:
                errors.append("Amount in figures is required")
            if not amount_words:
                errors.append("Amount in words is required")
            elif any(char.isdigit() for char in amount_words):
                errors.append("Amount in words cannot contain numbers")
            if not prepared_by:
                errors.append("Prepared by is required")
            if not prepared_signature:
                errors.append("Signature from preparer is required")
            if not reviewed_by:
                errors.append("Bill reviewed by is required")
            if not reviewed_signature:
                errors.append("Signature from reviewer is required")
            if prepared_date != today:
                errors.append(f"Prepared date must be today ({today})")
            if reviewed_date != today:
                errors.append(f"Reviewed date must be today ({today})")
            if not sender_email:
                errors.append("Your email address is required")
            elif not validate_email(sender_email)[0]:
                errors.append("Invalid email address format")
            
            if errors:
                st.markdown('<div class="error-box">', unsafe_allow_html=True)
                for error in errors:
                    st.error(f"❌ {error}")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                consignment_type = ""
                if is_mining:
                    consignment_type += "Mining "
                if is_agricultural:
                    consignment_type += "Agricultural "
                if other_type:
                    consignment_type += other_type
                if not consignment_type:
                    consignment_type = "Not specified"
                
                inspection_id = f"EPA-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                inspection_data = {
                    "inspection_id": inspection_id,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "consignment": consignment,
                    "agent_name": agent_name,
                    "contact": contact if contact else "Not provided",
                    "container_numbers": container_numbers,
                    "bill_of_lading": bill_of_lading,
                    "bill_of_entry": bill_of_entry if bill_of_entry else "Not provided",
                    "engine_items": engine_items,
                    "hp_rating": hp_rating,
                    "associated_parts": associated_parts if associated_parts else "None",
                    "proponent_name": proponent_name,
                    "nature_undertaking": nature_undertaking if nature_undertaking else "Not specified",
                    "location": location if location else "Not provided",
                    "address": address if address else "Not provided",
                    "contact_person": contact_person if contact_person else "Not provided",
                    "telephone": telephone if telephone else "Not provided",
                    "num_containers": num_containers,
                    "consignment_type": consignment_type,
                    "clearance_fee": "Yes" if clearance_fee else "No",
                    "penalty": "Yes" if penalty else "No",
                    "amount_figures": amount_figures,
                    "amount_words": amount_words,
                    "prepared_by": prepared_by,
                    "prepared_signature": prepared_signature,
                    "prepared_date": str(prepared_date),
                    "reviewed_by": reviewed_by,
                    "reviewed_signature": reviewed_signature,
                    "reviewed_date": str(reviewed_date)
                }
                
                with st.spinner(f"📧 Sending inspection report..."):
                    email_success, email_message = send_email_report(sender_email, inspection_data, st.session_state.photos)
                    
                    if email_success:
                        save_success, save_message = save_inspection_report(inspection_data, st.session_state.photos, email_sent=True)
                        st.session_state.email_sent_status = True
                        st.session_state.last_inspection_id = inspection_id
                        st.session_state.show_success = True
                        st.session_state.step = 'success'
                        st.rerun()
                    else:
                        st.session_state.email_sent_status = False
                        st.session_state.last_inspection_id = inspection_id
                        st.session_state.show_success = True
                        st.session_state.step = 'success'
                        st.rerun()
    
    if st.button("← Back to Photo Capture", use_container_width=True):
        st.session_state.step = 'photos'
        st.rerun()

st.markdown("---")
st.markdown("*SOP Checklist for Internal Use Only*")
st.caption(f"EPA Ghana - Consignment Inspection System | {datetime.now().year}")
