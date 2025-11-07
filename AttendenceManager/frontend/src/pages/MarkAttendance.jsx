import { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import Layout from '@/components/Layout';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { Calendar as CalendarIcon, CheckCircle, XCircle, Clock } from 'lucide-react';
import { format } from 'date-fns';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

export default function MarkAttendance({ user, onLogout }) {
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [attendance, setAttendance] = useState({});
  const [loading, setLoading] = useState(false);
  const [existingAttendance, setExistingAttendance] = useState({});

  useEffect(() => {
    fetchClasses();
  }, []);

  useEffect(() => {
    if (selectedClass) {
      fetchStudents();
      fetchExistingAttendance();
    }
  }, [selectedClass, selectedDate]);

  const fetchClasses = async () => {
    try {
      const response = await axios.get(`${API}/classes`);
      setClasses(response.data);
    } catch (error) {
      toast.error('Failed to fetch classes');
    }
  };

  const fetchStudents = async () => {
    try {
      const response = await axios.get(`${API}/students?class_id=${selectedClass}`);
      setStudents(response.data);
      // Initialize attendance state
      const initialAttendance = {};
      response.data.forEach(student => {
        initialAttendance[student.id] = 'present';
      });
      setAttendance(initialAttendance);
    } catch (error) {
      toast.error('Failed to fetch students');
    }
  };

  const fetchExistingAttendance = async () => {
    try {
      const dateStr = format(selectedDate, 'yyyy-MM-dd');
      const response = await axios.get(`${API}/attendance?class_id=${selectedClass}&date=${dateStr}`);
      const existing = {};
      response.data.forEach(record => {
        existing[record.student_id] = record.status;
      });
      setExistingAttendance(existing);
      // Update attendance state with existing data
      if (Object.keys(existing).length > 0) {
        setAttendance(prev => ({ ...prev, ...existing }));
      }
    } catch (error) {
      console.error('Failed to fetch existing attendance');
    }
  };

  const handleAttendanceChange = (studentId, status) => {
    setAttendance(prev => ({
      ...prev,
      [studentId]: status
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const dateStr = format(selectedDate, 'yyyy-MM-dd');
      const attendanceRecords = Object.entries(attendance).map(([studentId, status]) => ({
        student_id: studentId,
        status: status
      }));

      await axios.post(`${API}/attendance/bulk`, {
        class_id: selectedClass,
        date: dateStr,
        attendance_records: attendanceRecords
      });

      toast.success('Attendance marked successfully!');
      setExistingAttendance(attendance);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to mark attendance');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'present':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'absent':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'late':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  return (
    <Layout user={user} onLogout={onLogout} currentPage="attendance">
      <div className="space-y-6" data-testid="mark-attendance-page">
        <div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Mark Attendance</h1>
          <p className="text-gray-600">Record student attendance for your classes</p>
        </div>

        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle>Select Class and Date</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label htmlFor="class">Class</Label>
                <select
                  id="class"
                  data-testid="class-select"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={selectedClass}
                  onChange={(e) => setSelectedClass(e.target.value)}
                >
                  <option value="">Select a class</option>
                  {classes.map((cls) => (
                    <option key={cls.id} value={cls.id}>
                      {cls.name} - {cls.section}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Date</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      data-testid="date-picker-trigger"
                      variant="outline"
                      className="w-full justify-start text-left font-normal"
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {format(selectedDate, 'PPP')}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0">
                    <Calendar
                      mode="single"
                      selected={selectedDate}
                      onSelect={(date) => date && setSelectedDate(date)}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
            </div>
          </CardContent>
        </Card>

        {selectedClass && students.length > 0 && (
          <form onSubmit={handleSubmit}>
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <CardTitle>Students Attendance</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {students.map((student) => (
                    <div
                      key={student.id}
                      data-testid={`student-attendance-${student.id}`}
                      className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                      <div>
                        <p className="font-semibold text-gray-900">{student.name}</p>
                        <p className="text-sm text-gray-600">Roll No: {student.roll_number}</p>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          type="button"
                          data-testid={`present-${student.id}`}
                          onClick={() => handleAttendanceChange(student.id, 'present')}
                          className={`px-4 py-2 rounded-lg border-2 font-medium transition-all ${
                            attendance[student.id] === 'present'
                              ? getStatusColor('present')
                              : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          <CheckCircle className="w-4 h-4 inline mr-1" />
                          Present
                        </button>
                        <button
                          type="button"
                          data-testid={`absent-${student.id}`}
                          onClick={() => handleAttendanceChange(student.id, 'absent')}
                          className={`px-4 py-2 rounded-lg border-2 font-medium transition-all ${
                            attendance[student.id] === 'absent'
                              ? getStatusColor('absent')
                              : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          <XCircle className="w-4 h-4 inline mr-1" />
                          Absent
                        </button>
                        <button
                          type="button"
                          data-testid={`late-${student.id}`}
                          onClick={() => handleAttendanceChange(student.id, 'late')}
                          className={`px-4 py-2 rounded-lg border-2 font-medium transition-all ${
                            attendance[student.id] === 'late'
                              ? getStatusColor('late')
                              : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          <Clock className="w-4 h-4 inline mr-1" />
                          Late
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-6">
                  <Button
                    type="submit"
                    data-testid="submit-attendance-button"
                    className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 py-6 text-lg font-semibold shadow-lg"
                    disabled={loading}
                  >
                    {loading ? 'Saving...' : 'Save Attendance'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </form>
        )}

        {selectedClass && students.length === 0 && (
          <Card className="border-0 shadow-lg">
            <CardContent className="text-center py-12 text-gray-500">
              No students found in this class. Please add students first.
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
}
