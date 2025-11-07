from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ==================== MODELS ====================

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: str = "teacher"  # teacher or admin
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "teacher"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class Student(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    roll_number: str
    class_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StudentCreate(BaseModel):
    name: str
    roll_number: str
    class_id: str
    email: Optional[str] = None
    phone: Optional[str] = None

class Class(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    section: str
    subject: Optional[str] = None
    teacher_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ClassCreate(BaseModel):
    name: str
    section: str
    subject: Optional[str] = None

class Attendance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    class_id: str
    date: str  # YYYY-MM-DD format
    status: str  # present, absent, late
    marked_by: str  # teacher_id
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AttendanceCreate(BaseModel):
    student_id: str
    class_id: str
    date: str
    status: str
    remarks: Optional[str] = None

class BulkAttendanceCreate(BaseModel):
    class_id: str
    date: str
    attendance_records: List[dict]  # [{student_id, status, remarks}]

# ==================== AUTH HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user)

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=User)
async def register(user_input: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_input.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_pw = hash_password(user_input.password)
    
    # Create user
    user_dict = user_input.model_dump(exclude={"password"})
    user = User(**user_dict)
    
    doc = user.model_dump()
    doc['password'] = hashed_pw
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.users.insert_one(doc)
    return user

@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(credentials.password, user_doc['password']):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create access token
    access_token = create_access_token(data={"sub": user_doc['id']})
    
    # Remove password from user object
    user_doc.pop('password', None)
    if isinstance(user_doc['created_at'], str):
        user_doc['created_at'] = datetime.fromisoformat(user_doc['created_at'])
    
    user = User(**user_doc)
    
    return Token(access_token=access_token, token_type="bearer", user=user)

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# ==================== STUDENT ROUTES ====================

@api_router.post("/students", response_model=Student)
async def create_student(student_input: StudentCreate, current_user: User = Depends(get_current_user)):
    # Check for duplicate roll number in same class
    existing = await db.students.find_one({"roll_number": student_input.roll_number, "class_id": student_input.class_id})
    if existing:
        raise HTTPException(status_code=400, detail="Roll number already exists in this class")
    
    student = Student(**student_input.model_dump())
    doc = student.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.students.insert_one(doc)
    return student

@api_router.get("/students", response_model=List[Student])
async def get_students(class_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    query = {"class_id": class_id} if class_id else {}
    students = await db.students.find(query, {"_id": 0}).to_list(1000)
    
    for student in students:
        if isinstance(student['created_at'], str):
            student['created_at'] = datetime.fromisoformat(student['created_at'])
    
    return students

@api_router.get("/students/{student_id}", response_model=Student)
async def get_student(student_id: str, current_user: User = Depends(get_current_user)):
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if isinstance(student['created_at'], str):
        student['created_at'] = datetime.fromisoformat(student['created_at'])
    
    return Student(**student)

@api_router.put("/students/{student_id}", response_model=Student)
async def update_student(student_id: str, student_input: StudentCreate, current_user: User = Depends(get_current_user)):
    existing = await db.students.find_one({"id": student_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Student not found")
    
    update_data = student_input.model_dump()
    await db.students.update_one({"id": student_id}, {"$set": update_data})
    
    updated = await db.students.find_one({"id": student_id}, {"_id": 0})
    if isinstance(updated['created_at'], str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    
    return Student(**updated)

@api_router.delete("/students/{student_id}")
async def delete_student(student_id: str, current_user: User = Depends(get_current_user)):
    result = await db.students.delete_one({"id": student_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}

# ==================== CLASS ROUTES ====================

@api_router.post("/classes", response_model=Class)
async def create_class(class_input: ClassCreate, current_user: User = Depends(get_current_user)):
    class_dict = class_input.model_dump()
    class_dict['teacher_id'] = current_user.id
    
    class_obj = Class(**class_dict)
    doc = class_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.classes.insert_one(doc)
    return class_obj

@api_router.get("/classes", response_model=List[Class])
async def get_classes(current_user: User = Depends(get_current_user)):
    query = {} if current_user.role == "admin" else {"teacher_id": current_user.id}
    classes = await db.classes.find(query, {"_id": 0}).to_list(1000)
    
    for cls in classes:
        if isinstance(cls['created_at'], str):
            cls['created_at'] = datetime.fromisoformat(cls['created_at'])
    
    return classes

@api_router.get("/classes/{class_id}", response_model=Class)
async def get_class(class_id: str, current_user: User = Depends(get_current_user)):
    class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if isinstance(class_doc['created_at'], str):
        class_doc['created_at'] = datetime.fromisoformat(class_doc['created_at'])
    
    return Class(**class_doc)

@api_router.put("/classes/{class_id}", response_model=Class)
async def update_class(class_id: str, class_input: ClassCreate, current_user: User = Depends(get_current_user)):
    existing = await db.classes.find_one({"id": class_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and existing['teacher_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this class")
    
    update_data = class_input.model_dump()
    await db.classes.update_one({"id": class_id}, {"$set": update_data})
    
    updated = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if isinstance(updated['created_at'], str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    
    return Class(**updated)

@api_router.delete("/classes/{class_id}")
async def delete_class(class_id: str, current_user: User = Depends(get_current_user)):
    existing = await db.classes.find_one({"id": class_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and existing['teacher_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this class")
    
    result = await db.classes.delete_one({"id": class_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Class not found")
    return {"message": "Class deleted successfully"}

# ==================== ATTENDANCE ROUTES ====================

@api_router.post("/attendance", response_model=Attendance)
async def mark_attendance(attendance_input: AttendanceCreate, current_user: User = Depends(get_current_user)):
    # Check if attendance already exists for this student on this date
    existing = await db.attendance.find_one({
        "student_id": attendance_input.student_id,
        "class_id": attendance_input.class_id,
        "date": attendance_input.date
    })
    
    if existing:
        # Update existing attendance
        update_data = attendance_input.model_dump()
        update_data['marked_by'] = current_user.id
        update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        await db.attendance.update_one(
            {"id": existing['id']},
            {"$set": update_data}
        )
        
        updated = await db.attendance.find_one({"id": existing['id']}, {"_id": 0})
        if isinstance(updated['created_at'], str):
            updated['created_at'] = datetime.fromisoformat(updated['created_at'])
        if isinstance(updated['updated_at'], str):
            updated['updated_at'] = datetime.fromisoformat(updated['updated_at'])
        
        return Attendance(**updated)
    
    # Create new attendance record
    attendance_dict = attendance_input.model_dump()
    attendance_dict['marked_by'] = current_user.id
    
    attendance = Attendance(**attendance_dict)
    doc = attendance.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    
    await db.attendance.insert_one(doc)
    return attendance

@api_router.post("/attendance/bulk")
async def mark_bulk_attendance(bulk_input: BulkAttendanceCreate, current_user: User = Depends(get_current_user)):
    results = []
    
    for record in bulk_input.attendance_records:
        attendance_input = AttendanceCreate(
            student_id=record['student_id'],
            class_id=bulk_input.class_id,
            date=bulk_input.date,
            status=record['status'],
            remarks=record.get('remarks')
        )
        
        # Check if attendance already exists
        existing = await db.attendance.find_one({
            "student_id": attendance_input.student_id,
            "class_id": attendance_input.class_id,
            "date": attendance_input.date
        })
        
        if existing:
            # Update existing
            update_data = attendance_input.model_dump()
            update_data['marked_by'] = current_user.id
            update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            await db.attendance.update_one(
                {"id": existing['id']},
                {"$set": update_data}
            )
            results.append({"student_id": record['student_id'], "action": "updated"})
        else:
            # Create new
            attendance_dict = attendance_input.model_dump()
            attendance_dict['marked_by'] = current_user.id
            
            attendance = Attendance(**attendance_dict)
            doc = attendance.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            doc['updated_at'] = doc['updated_at'].isoformat()
            
            await db.attendance.insert_one(doc)
            results.append({"student_id": record['student_id'], "action": "created"})
    
    return {"message": "Bulk attendance marked successfully", "results": results}

@api_router.get("/attendance")
async def get_attendance(
    class_id: Optional[str] = None,
    student_id: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    
    if class_id:
        query['class_id'] = class_id
    if student_id:
        query['student_id'] = student_id
    if date:
        query['date'] = date
    elif start_date and end_date:
        query['date'] = {"$gte": start_date, "$lte": end_date}
    
    attendance_records = await db.attendance.find(query, {"_id": 0}).to_list(10000)
    
    for record in attendance_records:
        if isinstance(record['created_at'], str):
            record['created_at'] = datetime.fromisoformat(record['created_at'])
        if isinstance(record['updated_at'], str):
            record['updated_at'] = datetime.fromisoformat(record['updated_at'])
    
    return attendance_records

@api_router.get("/attendance/report")
async def get_attendance_report(
    class_id: str,
    start_date: str,
    end_date: str,
    current_user: User = Depends(get_current_user)
):
    # Get all students in the class
    students = await db.students.find({"class_id": class_id}, {"_id": 0}).to_list(1000)
    
    # Get attendance records for the date range
    attendance_records = await db.attendance.find({
        "class_id": class_id,
        "date": {"$gte": start_date, "$lte": end_date}
    }, {"_id": 0}).to_list(10000)
    
    # Calculate statistics for each student
    report = []
    for student in students:
        student_attendance = [r for r in attendance_records if r['student_id'] == student['id']]
        
        total_days = len(set([r['date'] for r in attendance_records]))
        present_count = len([r for r in student_attendance if r['status'] == 'present'])
        absent_count = len([r for r in student_attendance if r['status'] == 'absent'])
        late_count = len([r for r in student_attendance if r['status'] == 'late'])
        
        attendance_percentage = (present_count / total_days * 100) if total_days > 0 else 0
        
        report.append({
            "student_id": student['id'],
            "student_name": student['name'],
            "roll_number": student['roll_number'],
            "total_days": total_days,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "attendance_percentage": round(attendance_percentage, 2)
        })
    
    return {"class_id": class_id, "start_date": start_date, "end_date": end_date, "report": report}

# ==================== DASHBOARD STATS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    # Get counts
    total_classes = await db.classes.count_documents({} if current_user.role == "admin" else {"teacher_id": current_user.id})
    total_students = await db.students.count_documents({})
    
    # Get today's attendance
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_attendance = await db.attendance.count_documents({"date": today})
    
    # Get recent attendance records
    recent_attendance = await db.attendance.find({}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
    
    return {
        "total_classes": total_classes,
        "total_students": total_students,
        "today_attendance": today_attendance,
        "recent_attendance": recent_attendance
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
