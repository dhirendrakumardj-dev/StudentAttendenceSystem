import requests
import sys
from datetime import datetime, timedelta

class AttendanceSystemTester:
    def __init__(self, base_url="https://student-presence-37.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_data = {
            'class_id': None,
            'student_ids': [],
            'attendance_ids': []
        }

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except:
                    print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_register(self):
        """Test user registration"""
        timestamp = datetime.now().strftime('%H%M%S')
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "email": f"teacher_{timestamp}@school.com",
                "password": "TestPass123!",
                "name": f"Test Teacher {timestamp}",
                "role": "teacher"
            }
        )
        if success:
            self.user_id = response.get('id')
        return success

    def test_login(self, email, password):
        """Test login and get token"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            return True
        return False

    def test_get_me(self):
        """Test get current user"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_create_class(self):
        """Test creating a class"""
        success, response = self.run_test(
            "Create Class",
            "POST",
            "classes",
            200,
            data={
                "name": "Grade 10",
                "section": "A",
                "subject": "Mathematics"
            }
        )
        if success:
            self.test_data['class_id'] = response.get('id')
        return success

    def test_get_classes(self):
        """Test getting all classes"""
        success, response = self.run_test(
            "Get All Classes",
            "GET",
            "classes",
            200
        )
        return success

    def test_get_class(self):
        """Test getting a specific class"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        success, response = self.run_test(
            "Get Single Class",
            "GET",
            f"classes/{self.test_data['class_id']}",
            200
        )
        return success

    def test_update_class(self):
        """Test updating a class"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        success, response = self.run_test(
            "Update Class",
            "PUT",
            f"classes/{self.test_data['class_id']}",
            200,
            data={
                "name": "Grade 10",
                "section": "A",
                "subject": "Advanced Mathematics"
            }
        )
        return success

    def test_create_student(self):
        """Test creating a student"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        success, response = self.run_test(
            "Create Student",
            "POST",
            "students",
            200,
            data={
                "name": "John Doe",
                "roll_number": "001",
                "class_id": self.test_data['class_id'],
                "email": "john@example.com",
                "phone": "1234567890"
            }
        )
        if success:
            self.test_data['student_ids'].append(response.get('id'))
        return success

    def test_create_multiple_students(self):
        """Test creating multiple students"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        students = [
            {"name": "Jane Smith", "roll_number": "002"},
            {"name": "Bob Johnson", "roll_number": "003"}
        ]
        
        all_success = True
        for student in students:
            success, response = self.run_test(
                f"Create Student - {student['name']}",
                "POST",
                "students",
                200,
                data={
                    **student,
                    "class_id": self.test_data['class_id']
                }
            )
            if success:
                self.test_data['student_ids'].append(response.get('id'))
            else:
                all_success = False
        
        return all_success

    def test_get_students(self):
        """Test getting all students"""
        success, response = self.run_test(
            "Get All Students",
            "GET",
            "students",
            200
        )
        return success

    def test_get_students_by_class(self):
        """Test getting students by class"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        success, response = self.run_test(
            "Get Students by Class",
            "GET",
            "students",
            200,
            params={"class_id": self.test_data['class_id']}
        )
        return success

    def test_get_student(self):
        """Test getting a specific student"""
        if not self.test_data['student_ids']:
            print("⚠️  Skipping - No student ID available")
            return False
        
        success, response = self.run_test(
            "Get Single Student",
            "GET",
            f"students/{self.test_data['student_ids'][0]}",
            200
        )
        return success

    def test_update_student(self):
        """Test updating a student"""
        if not self.test_data['student_ids'] or not self.test_data['class_id']:
            print("⚠️  Skipping - No student ID available")
            return False
        
        success, response = self.run_test(
            "Update Student",
            "PUT",
            f"students/{self.test_data['student_ids'][0]}",
            200,
            data={
                "name": "John Doe Updated",
                "roll_number": "001",
                "class_id": self.test_data['class_id'],
                "email": "john.updated@example.com",
                "phone": "9876543210"
            }
        )
        return success

    def test_mark_attendance(self):
        """Test marking attendance for a single student"""
        if not self.test_data['student_ids'] or not self.test_data['class_id']:
            print("⚠️  Skipping - No student/class ID available")
            return False
        
        today = datetime.now().strftime("%Y-%m-%d")
        success, response = self.run_test(
            "Mark Single Attendance",
            "POST",
            "attendance",
            200,
            data={
                "student_id": self.test_data['student_ids'][0],
                "class_id": self.test_data['class_id'],
                "date": today,
                "status": "present",
                "remarks": "On time"
            }
        )
        return success

    def test_bulk_attendance(self):
        """Test marking bulk attendance"""
        if not self.test_data['student_ids'] or not self.test_data['class_id']:
            print("⚠️  Skipping - No student/class ID available")
            return False
        
        today = datetime.now().strftime("%Y-%m-%d")
        attendance_records = []
        for i, student_id in enumerate(self.test_data['student_ids']):
            status = ['present', 'absent', 'late'][i % 3]
            attendance_records.append({
                "student_id": student_id,
                "status": status
            })
        
        success, response = self.run_test(
            "Mark Bulk Attendance",
            "POST",
            "attendance/bulk",
            200,
            data={
                "class_id": self.test_data['class_id'],
                "date": today,
                "attendance_records": attendance_records
            }
        )
        return success

    def test_get_attendance(self):
        """Test getting attendance records"""
        success, response = self.run_test(
            "Get All Attendance",
            "GET",
            "attendance",
            200
        )
        return success

    def test_get_attendance_by_class(self):
        """Test getting attendance by class"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        success, response = self.run_test(
            "Get Attendance by Class",
            "GET",
            "attendance",
            200,
            params={"class_id": self.test_data['class_id']}
        )
        return success

    def test_get_attendance_by_date(self):
        """Test getting attendance by date"""
        today = datetime.now().strftime("%Y-%m-%d")
        success, response = self.run_test(
            "Get Attendance by Date",
            "GET",
            "attendance",
            200,
            params={"date": today}
        )
        return success

    def test_attendance_report(self):
        """Test generating attendance report"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        success, response = self.run_test(
            "Generate Attendance Report",
            "GET",
            "attendance/report",
            200,
            params={
                "class_id": self.test_data['class_id'],
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }
        )
        return success

    def test_dashboard_stats(self):
        """Test getting dashboard statistics"""
        success, response = self.run_test(
            "Get Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        return success

    def test_delete_student(self):
        """Test deleting a student"""
        if not self.test_data['student_ids']:
            print("⚠️  Skipping - No student ID available")
            return False
        
        # Delete the last student
        student_id = self.test_data['student_ids'][-1]
        success, response = self.run_test(
            "Delete Student",
            "DELETE",
            f"students/{student_id}",
            200
        )
        if success:
            self.test_data['student_ids'].pop()
        return success

    def test_delete_class(self):
        """Test deleting a class"""
        if not self.test_data['class_id']:
            print("⚠️  Skipping - No class ID available")
            return False
        
        success, response = self.run_test(
            "Delete Class",
            "DELETE",
            f"classes/{self.test_data['class_id']}",
            200
        )
        return success


def main():
    print("=" * 60)
    print("Student Attendance System - Backend API Testing")
    print("=" * 60)
    
    tester = AttendanceSystemTester()
    timestamp = datetime.now().strftime('%H%M%S')
    test_email = f"teacher_{timestamp}@school.com"
    test_password = "TestPass123!"

    # Authentication Tests
    print("\n" + "=" * 60)
    print("AUTHENTICATION TESTS")
    print("=" * 60)
    tester.test_register()
    tester.test_login(test_email, test_password)
    tester.test_get_me()

    # Class Management Tests
    print("\n" + "=" * 60)
    print("CLASS MANAGEMENT TESTS")
    print("=" * 60)
    tester.test_create_class()
    tester.test_get_classes()
    tester.test_get_class()
    tester.test_update_class()

    # Student Management Tests
    print("\n" + "=" * 60)
    print("STUDENT MANAGEMENT TESTS")
    print("=" * 60)
    tester.test_create_student()
    tester.test_create_multiple_students()
    tester.test_get_students()
    tester.test_get_students_by_class()
    tester.test_get_student()
    tester.test_update_student()

    # Attendance Tests
    print("\n" + "=" * 60)
    print("ATTENDANCE TESTS")
    print("=" * 60)
    tester.test_mark_attendance()
    tester.test_bulk_attendance()
    tester.test_get_attendance()
    tester.test_get_attendance_by_class()
    tester.test_get_attendance_by_date()
    tester.test_attendance_report()

    # Dashboard Tests
    print("\n" + "=" * 60)
    print("DASHBOARD TESTS")
    print("=" * 60)
    tester.test_dashboard_stats()

    # Cleanup Tests
    print("\n" + "=" * 60)
    print("CLEANUP TESTS")
    print("=" * 60)
    tester.test_delete_student()
    tester.test_delete_class()

    # Print final results
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"📊 Tests Run: {tester.tests_run}")
    print(f"✅ Tests Passed: {tester.tests_passed}")
    print(f"❌ Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"📈 Success Rate: {(tester.tests_passed / tester.tests_run * 100):.2f}%")
    print("=" * 60)

    return 0 if tester.tests_passed == tester.tests_run else 1


if __name__ == "__main__":
    sys.exit(main())
