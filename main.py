import streamlit as st
import mysql.connector
import pandas as pd
from datetime import date
import math

# --- Database Connection ---
# This function centralizes the database connection logic.
# You can easily change the details here.
def get_db_connection():
    """Establishes and returns a MySQL database connection."""
    timeout = 10
    try:
        connection = mysql.connector.connect(
            charset="utf8mb4",
            connection_timeout=timeout,
            database="college_attendance",
            host=st.secrets["host"],
            password=st.secrets["password"],
            port=st.secrets["port"],
            user=st.secrets["user"],
        )
        return connection
    except mysql.connector.Error as e:
        st.error(f"Error connecting to MySQL: {e}")
        return None

# --- Main Streamlit App Layout ---
st.title("College Attendance Tracker")
st.markdown("---")
st.warning("This site is specifically for the use of P Devdat.\nPlease do not tamper or add any data into the site")
# --- Sidebar for Navigation ---
st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", [ "Mark Attendance", "View Progress","Add Course",])
st.sidebar.markdown("---")
st.sidebar.info("Attendance Deadline: 75%\n\nSafety Net: 85%")


# --- Function to Add New Courses ---
if page == "Add Course":
    st.header("Add New Course")
    conn = get_db_connection()
    if conn:
        new_course_name = st.text_input("Course Name")
        if st.button("Add Course"):
            if new_course_name:
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO courses (course_name) VALUES (%s)", (new_course_name,))
                    conn.commit()
                    st.success(f"Successfully added '{new_course_name}'!")
                except mysql.connector.Error as err:
                    st.error(f"Error: {err}")
                    conn.rollback()
                finally:
                    cursor.close()
                    conn.close()
            else:
                st.warning("Please enter a course name.")

# --- Function to Mark Daily Attendance ---
elif page == "Mark Attendance":
    st.header("Mark Daily Attendance")
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT course_id, course_name FROM courses")
        courses = cursor.fetchall()
        cursor.close()

        if courses:
            course_options = {course['course_name']: course['course_id'] for course in courses}
            
            with st.form(key='attendance_form'):
                selected_course_name = st.selectbox("Select a Course", list(course_options.keys()))
                selected_course_id = course_options[selected_course_name]

                class_date = st.date_input("Date", date.today())
                
                cursor = conn.cursor()
                query = "SELECT MAX(class_session) FROM attendance WHERE course_id = %s AND class_date = %s"
                cursor.execute(query, (selected_course_id, class_date))
                last_session = cursor.fetchone()[0]
                next_session = (last_session + 1) if last_session else 1
                cursor.close()

                class_session = st.number_input("Class Session Number", min_value=1, step=1, value=next_session)
                
                attendance_status = st.radio("Attendance Status", ("present", "absent"))

                submitted = st.form_submit_button("Submit Attendance")

            if submitted:
                cursor = conn.cursor()
                try:
                    query = "INSERT INTO attendance (course_id, class_date, class_session, status) VALUES (%s, %s, %s, %s)"
                    cursor.execute(query, (selected_course_id, class_date, class_session, attendance_status))
                    conn.commit()
                    st.success(f"Attendance for '{selected_course_name}' on {class_date}, Session {class_session} marked as '{attendance_status}'.")
                    
                    st.rerun()
                except mysql.connector.Error as err:
                    if err.errno == mysql.connector.errorcode.ER_DUP_ENTRY:
                        st.warning(f"Attendance for '{selected_course_name}' on {class_date}, Session {class_session} has already been recorded.")
                    else:
                        st.error(f"Error: {err}")
                    conn.rollback()
                finally:
                    cursor.close()
                    conn.close()
        else:
            st.warning("No courses found. Please add a course first.")

# --- Function to View Progress ---
elif page == "View Progress":
    st.header("Attendance Progress")
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Get all courses
        cursor.execute("SELECT course_id, course_name FROM courses")
        courses = cursor.fetchall()

        if courses:
            for course in courses:
                st.subheader(course['course_name'])

                # Get total classes and present classes for the course
                query_stats = """
                    SELECT
                        COUNT(*) as total_classes,
                        SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_classes
                    FROM attendance
                    WHERE course_id = %s;
                """
                cursor.execute(query_stats, (course['course_id'],))
                stats = cursor.fetchone()
                
                if stats and stats['total_classes'] is not None and stats['present_classes'] is not None:
                    
                    # Explicitly cast the database values to standard Python integers
                    total_classes = int(stats['total_classes'])
                    present_classes = int(stats['present_classes'])

                    if total_classes > 0:
                        attendance_percentage = (present_classes / total_classes) * 100
                        st.write(f"Total Classes: {total_classes} | Classes Attended: {present_classes}")
                        st.write(f"Attendance Percentage: **{attendance_percentage:.2f}%**")

                        # Display the progress bar and status
                        progress_value = float(attendance_percentage) / 100
                        
                        if attendance_percentage >= 85:
                            st.progress(progress_value)
                            st.success(f"Excellent! Attendance is above the 85% safety net.")
                        elif attendance_percentage >= 75:
                            st.progress(progress_value)
                            st.warning(f"**Warning!** Attendance is below the 85% safety net.")
                        else:
                            st.progress(progress_value)
                            st.error(f"**Action Required!** Attendance is below the 75% deadline.")
                        
                        # --- Bunk Calculator Feature (always available in an expander) ---
                        with st.expander("Bunk Calculator"):
                            if total_classes >= 0:
                                hypothetical_total_classes = total_classes + 1
                                hypothetical_present_classes = present_classes
                                
                                hypothetical_percentage = (hypothetical_present_classes / hypothetical_total_classes) * 100
                                
                                st.write(f"If you bunk one class, your attendance would be **{hypothetical_percentage:.2f}%**.")
                                
                                if hypothetical_percentage >= 85:
                                    st.success("You can safely bunk this class without dropping below the 85% safety net.")
                                elif hypothetical_percentage >= 75:
                                    # --- New Calculation for Recovery after bunking ---
                                    st.warning("Bunking this class will keep you above the 75% deadline, but you will drop further below the 85% safety net.")
                                    
                                    try:
                                        # Calculate how many classes are needed to get back to 85% after the bunk
                                        required_recovery_classes = math.ceil((0.85 * hypothetical_total_classes - hypothetical_present_classes) / (1 - 0.85))
                                        if required_recovery_classes > 0:
                                            st.info(f"You would need to attend **{required_recovery_classes}** consecutive classes to get back above 85%.")
                                    except ZeroDivisionError:
                                        pass
                                else:
                                    st.error("Bunking this class will cause your attendance to drop below the critical 75% deadline. **Do not bunk!**")

                        # --- Attendance Recovery Plan (only appears when needed) ---
                        if attendance_percentage < 85:
                            with st.expander("Show Attendance Strategy"):
                                st.subheader("Attendance Recovery Plan")
                                
                                try:
                                    required_present_classes = math.ceil((0.85 * total_classes - present_classes) / (1 - 0.85))
                                except ZeroDivisionError:
                                    required_present_classes = 0

                                if required_present_classes > 0:
                                    st.info(f"You need to attend **{required_present_classes}** consecutive classes to bring your attendance above the 85% safety net.")
                                else:
                                    st.info("Your attendance is low, but you are not far from the target. The next class you attend will improve your percentage.")
                    else:
                        st.info("No attendance records for this course yet.")
                else:
                    st.info("No attendance records for this course yet.")
            
            cursor.close()
            conn.close()

        else:
            st.warning("No courses found. Please add a course first to view progress.")

        # --- Export to CSV feature ---
        st.markdown("---")
        st.subheader("Export Data")
        
        conn = get_db_connection()
        if conn:
            query = """
            SELECT
                a.attendance_id,
                c.course_name AS Course,
                a.class_date,
                a.class_session,
                a.status
            FROM attendance AS a
            JOIN courses AS c
                ON a.course_id = c.course_id;
            """
            
            df = pd.read_sql(query, conn)
            
            if not df.empty:
                st.download_button(
                    label="Download Attendance Data as CSV",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name='attendance_data.csv',
                    mime='text/csv'
                )
            else:
                st.info("No data to export yet. Please add some attendance records.")
            
            conn.close()

