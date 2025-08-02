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

# --- Sidebar for Navigation ---
st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["Add Course", "Mark Attendance", "View Progress"])
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
            selected_course_name = st.selectbox("Select a Course", list(course_options.keys()))
            selected_course_id = course_options[selected_course_name]

            class_date = st.date_input("Date", date.today())
            attendance_status = st.radio("Attendance Status", ("present", "absent"))

            if st.button("Submit Attendance"):
                cursor = conn.cursor()
                try:
                    query = "INSERT INTO attendance (course_id, class_date, status) VALUES (%s, %s, %s)"
                    cursor.execute(query, (selected_course_id, class_date, attendance_status))
                    conn.commit()
                    st.success(f"Attendance for '{selected_course_name}' on {class_date} marked as '{attendance_status}'.")
                except mysql.connector.Error as err:
                    if err.errno == mysql.connector.errorcode.ER_DUP_ENTRY:
                        st.warning(f"Attendance for '{selected_course_name}' on {class_date} has already been recorded.")
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
                
                total_classes = stats['total_classes']
                present_classes = stats['present_classes']

                if total_classes > 0:
                    attendance_percentage = (present_classes / total_classes) * 100
                    st.write(f"Total Classes: {total_classes} | Classes Attended: {present_classes}")
                    st.write(f"Attendance Percentage: **{attendance_percentage:.2f}%**")

                    # Display the progress bar and status
                    progress_value = attendance_percentage / 100
                    
                    if attendance_percentage >= 85:
                        bar_color = "green"
                    elif attendance_percentage >= 75:
                        bar_color = "orange"
                    else:
                        bar_color = "red"
                    
                    st.progress(progress_value)
                    
                    if attendance_percentage < 75:
                        st.error(f"**Action Required!** Attendance is below the 75% deadline.")
                    elif attendance_percentage < 85:
                        st.warning(f"**Warning!** Attendance is below the 85% safety net.")
                    else:
                        st.success(f"Excellent! Attendance is above the 85% safety net.")

                    # --- New Calculation Logic ---
                    # Calculate how many more classes are needed to reach 85%
                    if attendance_percentage < 85:
                        st.markdown("---")
                        st.subheader("Attendance Recovery Plan")
                        
                        # The formula is (present + x) / (total + x) = 0.85
                        # where x is the number of classes we need to attend.
                        # Solving for x:
                        # present + x = 0.85 * (total + x)
                        # present + x = 0.85*total + 0.85*x
                        # x - 0.85*x = 0.85*total - present
                        # 0.15*x = 0.85*total - present
                        # x = (0.85*total - present) / 0.15
                        
                        required_present_classes = math.ceil((0.85 * total_classes - present_classes) / (1 - 0.85))
                        
                        # Check if a positive number of classes is even possible
                        if required_present_classes > 0:
                             st.info(f"You need to attend **{required_present_classes}** consecutive classes to bring your attendance above the 85% safety net.")
                        else:
                             st.info("Your attendance is low, but you are not far from the target. The next class you attend will improve your percentage.")

                else:
                    st.info("No attendance records for this course yet.")
            
            cursor.close()
            conn.close()

        else:
            st.warning("No courses found. Please add a course first to view progress.")
