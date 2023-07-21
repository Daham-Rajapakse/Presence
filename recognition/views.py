import datetime
import math
import os
import pickle
import time

import cv2
import dlib
import face_recognition
import imutils
import matplotlib as mpl
import matplotlib.pyplot as plt
# import mpld3
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from attendance_system_facial_recognition.settings import BASE_DIR
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import render, redirect
from django_pandas.io import read_frame
from face_recognition.face_recognition_cli import image_files_in_folder
from imutils import face_utils
from imutils.face_utils import FaceAligner
from imutils.face_utils import rect_to_bb
from imutils.video import VideoStream
from matplotlib import rcParams
from pandas.plotting import register_matplotlib_converters
from sklearn.manifold import TSNE
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from users.models import Present, Time

from .forms import usernameForm, DateForm, UsernameAndDateForm, DateForm_2

mpl.use('Agg')


# utility functions:
def username_present(username):
    if User.objects.filter(username=username).exists():
        return True

    return False


def create_dataset(username):
    id = username
    if (os.path.exists('face_recognition_data/training_dataset/{}/'.format(id)) == False):
        os.makedirs('face_recognition_data/training_dataset/{}/'.format(id))
    directory = 'face_recognition_data/training_dataset/{}/'.format(id)

    # Detect face
    # Loading the HOG face detector and the shape predictpr for allignment

    print("[INFO] Loading the facial detector")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(
        'face_recognition_data/shape_predictor_68_face_landmarks.dat')  # Add path to the shape predictor ######CHANGE TO RELATIVE PATH LATER
    fa = FaceAligner(predictor, desiredFaceWidth=96)
    # capture images from the webcam and process and detect the face
    # Initialize the video stream
    print("[INFO] Initializing Video stream")
    vs = VideoStream(src=0).start()
    # time.sleep(2.0) ####CHECK######

    # Our identifier
    # We will put the id here and we will store the id with a face, so that later we can identify whose face it is

    # Our dataset naming counter
    sampleNum = 0
    # Capturing the faces one by one and detect the faces and showing it on the window
    while (True):
        # Capturing the image
        # vs.read each frame
        frame = vs.read()
        # Resize each image
        frame = imutils.resize(frame, width=800)
        # the returned img is a colored image but for the classifier to work we need a greyscale image
        # to convert
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # To store the faces
        # This will detect all the images in the current frame, and it will return the coordinates of the faces
        # Takes in image and some other parameter for accurate result
        faces = detector(gray_frame, 0)
        # In above 'faces' variable there can be multiple faces so we have to get each and every face and draw a rectangle around it.

        for face in faces:
            print("inside for loop")
            (x, y, w, h) = face_utils.rect_to_bb(face)

            face_aligned = fa.align(frame, gray_frame, face)
            # Whenever the program captures the face, we will write that is a folder
            # Before capturing the face, we need to tell the script whose face it is
            # For that we will need an identifier, here we call it id
            # So now we captured a face, we need to write it in a file
            sampleNum = sampleNum + 1
            # Saving the image dataset, but only the face part, cropping the rest

            if face is None:
                print("face is none")
                continue

            cv2.imwrite(directory + '/' + str(sampleNum) + '.jpg', face_aligned)
            face_aligned = imutils.resize(face_aligned, width=400)
            # cv2.imshow("Image Captured",face_aligned)
            # @params the initial point of the rectangle will be x,y and
            # @params end point will be x+width and y+height
            # @params along with color of the rectangle
            # @params thickness of the rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 1)
            # Before continuing to the next loop, I want to give it a little pause
            # waitKey of 100 millisecond
            cv2.waitKey(50)

        # Showing the image in another window
        # Creates a window with window name "Face" and with the image img
        cv2.imshow("Add Images", frame)
        # Before closing it we need to give a wait command, otherwise the open cv wont work
        # @params with the millisecond of delay 1
        cv2.waitKey(1)
        # To get out of the loop
        if (sampleNum > 300):
            break

    # Stoping the videostream
    vs.stop()
    # destroying all the windows
    cv2.destroyAllWindows()


def predict(face_aligned, svc, threshold=0.7):
    face_encodings = np.zeros((1, 128))
    try:
        x_face_locations = face_recognition.face_locations(face_aligned)
        faces_encodings = face_recognition.face_encodings(face_aligned, known_face_locations=x_face_locations)
        if (len(faces_encodings) == 0):
            return ([-1], [0])

    except:

        return ([-1], [0])

    prob = svc.predict_proba(faces_encodings)
    result = np.where(prob[0] == np.amax(prob[0]))
    if (prob[0][result[0]] <= threshold):
        return ([-1], prob[0][result[0]])

    return (result[0], prob[0][result[0]])


def vizualize_Data(embedded, targets, ):
    X_embedded = TSNE(n_components=2).fit_transform(embedded)

    for i, t in enumerate(set(targets)):
        idx = targets == t
        plt.scatter(X_embedded[idx, 0], X_embedded[idx, 1], label=t)

    plt.legend(bbox_to_anchor=(1, 1));
    rcParams.update({'figure.autolayout': True})
    plt.tight_layout()
    plt.savefig('./recognition/static/recognition/img/training_visualisation.png')
    plt.close()




# used
def hours_vs_employee_given_date(present_qs, time_qs):
    register_matplotlib_converters()
    df_hours = []
    df_break_hours = []
    df_username = []
    qs = present_qs

    for obj in qs:
        user = obj.user
        times_in = time_qs.filter(user=user).filter(out=False)
        times_out = time_qs.filter(user=user).filter(out=True)
        times_all = time_qs.filter(user=user)
        obj.time_in = None
        obj.time_out = None
        obj.hours = 0
        obj.hours = 0
        if (len(times_in) > 0):
            obj.time_in = times_in.first().time
        if (len(times_out) > 0):
            obj.time_out = times_out.last().time
        if (obj.time_in is not None and obj.time_out is not None):
            ti = obj.time_in
            to = obj.time_out
            hours = ((to - ti).total_seconds()) / 3600
            obj.hours = hours
        else:
            obj.hours = 0
        (check, break_hourss) = check_validity_times(times_all)
        if check:
            obj.break_hours = break_hourss


        else:
            obj.break_hours = 0

        df_hours.append(obj.hours)
        df_username.append(user.username)
        df_break_hours.append(obj.break_hours)
        obj.hours = convert_hours_to_hours_mins(obj.hours)
        obj.break_hours = convert_hours_to_hours_mins(obj.break_hours)

    df = read_frame(qs)
    df['hours'] = df_hours
    df['username'] = df_username
    df["break_hours"] = df_break_hours

    sns.barplot(data=df, x='username', y='hours')
    plt.xticks(rotation='vertical')
    rcParams.update({'figure.autolayout': True})
    plt.tight_layout()
    plt.savefig('./recognition/static/recognition/img/attendance_graphs/hours_vs_employee/1.png')
    plt.close()
    return qs


def total_number_employees():
    qs = User.objects.all()
    return (len(qs) - 1)


# -1 to account for admin


def employees_present_today():
    today = datetime.date.today()
    qs = Present.objects.filter(date=today).filter(present=True)
    return len(qs)


# used
def this_week_emp_count_vs_date():
    today = datetime.date.today()
    some_day_last_week = today - datetime.timedelta(days=7)
    monday_of_last_week = some_day_last_week - datetime.timedelta(days=(some_day_last_week.isocalendar()[2] - 1))
    monday_of_this_week = monday_of_last_week + datetime.timedelta(days=7)
    qs = Present.objects.filter(date__gte=monday_of_this_week).filter(date__lte=today)
    str_dates = []
    emp_count = []
    str_dates_all = []
    emp_cnt_all = []
    cnt = 0

    for obj in qs:
        date = obj.date
        str_dates.append(str(date))
        qs = Present.objects.filter(date=date).filter(present=True)
        emp_count.append(len(qs))

    while (cnt < 5):

        date = str(monday_of_this_week + datetime.timedelta(days=cnt))
        cnt += 1
        str_dates_all.append(date)
        if (str_dates.count(date)) > 0:
            idx = str_dates.index(date)

            emp_cnt_all.append(emp_count[idx])
        else:
            emp_cnt_all.append(0)

    df = pd.DataFrame()
    df["date"] = str_dates_all
    df["Number of employees"] = emp_cnt_all

    sns.lineplot(data=df, x='date', y='Number of employees')
    plt.savefig('./recognition/static/recognition/img/attendance_graphs/this_week/1.png')
    plt.close()


# used
def last_week_emp_count_vs_date():
    today = datetime.date.today()
    some_day_last_week = today - datetime.timedelta(days=7)
    monday_of_last_week = some_day_last_week - datetime.timedelta(days=(some_day_last_week.isocalendar()[2] - 1))
    monday_of_this_week = monday_of_last_week + datetime.timedelta(days=7)
    qs = Present.objects.filter(date__gte=monday_of_last_week).filter(date__lt=monday_of_this_week)
    str_dates = []
    emp_count = []

    str_dates_all = []
    emp_cnt_all = []
    cnt = 0

    for obj in qs:
        date = obj.date
        str_dates.append(str(date))
        qs = Present.objects.filter(date=date).filter(present=True)
        emp_count.append(len(qs))

    while (cnt < 5):

        date = str(monday_of_last_week + datetime.timedelta(days=cnt))
        cnt += 1
        str_dates_all.append(date)
        if (str_dates.count(date)) > 0:
            idx = str_dates.index(date)

            emp_cnt_all.append(emp_count[idx])

        else:
            emp_cnt_all.append(0)

    df = pd.DataFrame()
    df["date"] = str_dates_all
    df["emp_count"] = emp_cnt_all

    sns.lineplot(data=df, x='date', y='emp_count')
    plt.savefig('./recognition/static/recognition/img/attendance_graphs/last_week/1.png')
    plt.close()


# Create your views here.
def home(request):
    return render(request, 'recognition/home.html')


@login_required
def dashboard(request):
    if (request.user.username == 'admin'):
        print("admin")
        return render(request, 'recognition/admin_dashboard.html')
    else:
        print("not admin")

        return render(request, 'recognition/employee_dashboard.html')


@login_required
def add_photos(request):
    if request.user.username != 'admin':
        return redirect('not-authorised')
    if request.method == 'POST':
        form = usernameForm(request.POST)
        data = request.POST.copy()
        username = data.get('username')
        if username_present(username):
            create_dataset(username)
            messages.success(request, f'Dataset Created')
            return redirect('add-photos')
        else:
            messages.warning(request, f'No such username found. Please register employee first.')
            return redirect('dashboard')


    else:

        form = usernameForm()
        return render(request, 'recognition/add_photos.html', {'form': form})


def mark_your_attendance(request):
    detector = dlib.get_frontal_face_detector()

    predictor = dlib.shape_predictor(
        'face_recognition_data/shape_predictor_68_face_landmarks.dat')  # Add path to the shape predictor ######CHANGE TO RELATIVE PATH LATER
    svc_save_path = "face_recognition_data/svc.sav"

    with open(svc_save_path, 'rb') as f:
        svc = pickle.load(f)
    fa = FaceAligner(predictor, desiredFaceWidth=96)
    encoder = LabelEncoder()
    encoder.classes_ = np.load('face_recognition_data/classes.npy')

    faces_encodings = np.zeros((1, 128))
    no_of_faces = len(svc.predict_proba(faces_encodings)[0])
    count = dict()
    present = dict()
    log_time = dict()
    start = dict()
    for i in range(no_of_faces):
        count[encoder.inverse_transform([i])[0]] = 0
        present[encoder.inverse_transform([i])[0]] = False

    vs = VideoStream(src=0).start()

    sampleNum = 0

    while (True):

        frame = vs.read()

        frame = imutils.resize(frame, width=800)

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = detector(gray_frame, 0)

        for face in faces:
            print("INFO : inside for loop")
            (x, y, w, h) = face_utils.rect_to_bb(face)

            face_aligned = fa.align(frame, gray_frame, face)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 1)

            (pred, prob) = predict(face_aligned, svc)

            if (pred != [-1]):

                person_name = encoder.inverse_transform(np.ravel([pred]))[0]
                pred = person_name
                if count[pred] == 0:
                    start[pred] = time.time()
                    count[pred] = count.get(pred, 0) + 1

                if count[pred] == 4 and (time.time() - start[pred]) > 1.2:
                    count[pred] = 0
                else:
                    # if count[pred] == 4 and (time.time()-start) <= 1.5:
                    present[pred] = True
                    log_time[pred] = datetime.datetime.now()
                    count[pred] = count.get(pred, 0) + 1
                    print(pred, present[pred], count[pred])
                cv2.putText(frame, str(person_name) + str(prob), (x + 6, y + h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (0, 255, 0), 1)
                
                # Display the detected face with the name for 10 seconds
                cv2.imshow("Detected Face - " + person_name, cv2.resize(face_aligned, (300, 300)))  # Resize the window to 300x300
                cv2.waitKey(10000)
                cv2.destroyWindow("Detected Face - " + person_name)

                # Create a black background image with larger dimensions
                background_color = (0, 0, 0)
                background_image = np.full((150, 700, 3), background_color, dtype=np.uint8)

                # Add text to the image
                font = cv2.FONT_HERSHEY_SIMPLEX
                text = person_name.title() + " Your Attendance is marked"  # Modify this text as needed
                text_color = (255, 255, 255)  # White color for the text
                text_size = cv2.getTextSize(text, font, 1, 2)[0]
                text_x = (background_image.shape[1] - text_size[0]) // 2
                text_y = (background_image.shape[0] + text_size[1]) // 3
                cv2.putText(background_image, text, (text_x, text_y), font, 1, text_color, 2, cv2.LINE_AA)

                # Display the image in a window for 10 seconds
                cv2.imshow("Face Detected", background_image)
                update_attendance_in_db_in(present)
                cv2.waitKey(5000)
                cv2.destroyWindow("Face Detected")

                vs.stop()  # Stop the video stream
                cv2.destroyAllWindows()  # Close all windows
                return redirect('home')  # Redirect to the desired page after detecting a face

                
                #break  # Exit the for loop after detecting a face

            else:
                person_name = "unknown"
                cv2.putText(frame, str(person_name), (x + 6, y + h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # cv2.putText()
        # Before continuing to the next loop, I want to give it a little pause
        # waitKey of 100 millisecond
        # cv2.waitKey(50)

        # Showing the image in another window
        # Creates a window with window name "Face" and with the image img
        cv2.imshow("Mark Attendance - In - Press q to exit", frame)
        # Before closing it we need to give a wait command, otherwise the open cv wont work
        # @params with the millisecond of delay 1
        # cv2.waitKey(1)
        # To get out of the loop
        key = cv2.waitKey(50) & 0xFF
        if (key == ord("q")):
            break

    # Stoping the videostream
    vs.stop()

    # destroying all the windows
    cv2.destroyAllWindows()
    update_attendance_in_db_in(present)
    return redirect('home')


def mark_your_attendance_out(request):
    detector = dlib.get_frontal_face_detector()

    predictor = dlib.shape_predictor(
        'face_recognition_data/shape_predictor_68_face_landmarks.dat')  # Add path to the shape predictor ######CHANGE TO RELATIVE PATH LATER
    svc_save_path = "face_recognition_data/svc.sav"

    with open(svc_save_path, 'rb') as f:
        svc = pickle.load(f)
    fa = FaceAligner(predictor, desiredFaceWidth=96)
    encoder = LabelEncoder()
    encoder.classes_ = np.load('face_recognition_data/classes.npy')

    faces_encodings = np.zeros((1, 128))
    no_of_faces = len(svc.predict_proba(faces_encodings)[0])
    count = dict()
    present = dict()
    log_time = dict()
    start = dict()
    for i in range(no_of_faces):
        count[encoder.inverse_transform([i])[0]] = 0
        present[encoder.inverse_transform([i])[0]] = False

    vs = VideoStream(src=0).start()

    sampleNum = 0

    while (True):

        frame = vs.read()

        frame = imutils.resize(frame, width=800)

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = detector(gray_frame, 0)

        for face in faces:
            print("INFO : inside for loop")
            (x, y, w, h) = face_utils.rect_to_bb(face)

            face_aligned = fa.align(frame, gray_frame, face)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 1)

            (pred, prob) = predict(face_aligned, svc)

            if (pred != [-1]):

                person_name = encoder.inverse_transform(np.ravel([pred]))[0]
                pred = person_name
                if count[pred] == 0:
                    start[pred] = time.time()
                    count[pred] = count.get(pred, 0) + 1

                if count[pred] == 4 and (time.time() - start[pred]) > 1.5:
                    count[pred] = 0
                else:
                    # if count[pred] == 4 and (time.time()-start) <= 1.5:
                    present[pred] = True
                    log_time[pred] = datetime.datetime.now()
                    count[pred] = count.get(pred, 0) + 1
                    print(pred, present[pred], count[pred])
                cv2.putText(frame, str(person_name) + str(prob), (x + 6, y + h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (0, 255, 0), 1)
                # Show the face detected message for 5 seconds (5000 milliseconds)
                # Display the detected face with the name for 5 seconds
                cv2.imshow("Detected Face - " + person_name, cv2.resize(face_aligned, (300, 300)))  # Resize the window to 300x300
                cv2.waitKey(5000)
                cv2.destroyWindow("Detected Face - " + person_name)

                # Create a black background image with larger dimensions
                background_color = (0, 0, 0)
                background_image = np.full((150, 700, 3), background_color, dtype=np.uint8)

                # Add text to the image
                font = cv2.FONT_HERSHEY_SIMPLEX
                text = person_name.title() + " Your Attendance-Out is marked"  # Modify this text as needed
                text_color = (255, 255, 255)  # White color for the text
                text_size = cv2.getTextSize(text, font, 1, 2)[0]
                text_x = (background_image.shape[1] - text_size[0]) // 2
                text_y = (background_image.shape[0] + text_size[1]) // 3
                cv2.putText(background_image, text, (text_x, text_y), font, 1, text_color, 2, cv2.LINE_AA)

                # Display the image in a window for 5 seconds
                cv2.imshow("Face Detected", background_image)
                update_attendance_in_db_out(present)
                cv2.waitKey(5000)
                
            else:
                person_name = "unknown"
                cv2.putText(frame, str(person_name), (x + 6, y + h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # cv2.putText()
        # Before continuing to the next loop, I want to give it a little pause
        # waitKey of 100 millisecond
        # cv2.waitKey(50)

        # Showing the image in another window
        # Creates a window with window name "Face" and with the image img
        cv2.imshow("Mark Attendance- Out - Press q to exit", frame)
        # Before closing it we need to give a wait command, otherwise the open cv wont work
        # @params with the millisecond of delay 1
        # cv2.waitKey(1)
        # To get out of the loop
        key = cv2.waitKey(50) & 0xFF
        if (key == ord("q")):
            break

    # Stoping the videostream
    vs.stop()

    # destroying all the windows
    cv2.destroyAllWindows()
    update_attendance_in_db_out(present)
    return redirect('home')


def predict(face_aligned, svc, threshold=0.7):
    face_encodings = np.zeros((1, 128))
    try:
        x_face_locations = face_recognition.face_locations(face_aligned)
        faces_encodings = face_recognition.face_encodings(face_aligned, known_face_locations=x_face_locations)
        if (len(faces_encodings) == 0):
            return ([-1], [0])

    except:

        return ([-1], [0])

    prob = svc.predict_proba(faces_encodings)
    result = np.where(prob[0] == np.amax(prob[0]))
    if (prob[0][result[0]] <= threshold):
        return ([-1], prob[0][result[0]])

    return (result[0], prob[0][result[0]])

@login_required
def not_authorised(request):
    return render(request, 'recognition/not_authorised.html')


@login_required
def view_attendance_home(request):
    total_num_of_emp = total_number_employees()
    emp_present_today = employees_present_today()
    this_week_emp_count_vs_date()
    last_week_emp_count_vs_date()
    return render(request, "recognition/view_attendance_home.html",
                  {'total_num_of_emp': total_num_of_emp, 'emp_present_today': emp_present_today})


@login_required
def view_attendance_date(request):
    if request.user.username != 'admin':
        return redirect('not-authorised')
    qs = None
    time_qs = None
    present_qs = None

    if request.method == 'POST':
        form = DateForm(request.POST)
        if form.is_valid():
            date = form.cleaned_data.get('date')
            print("date:" + str(date))
            time_qs = Time.objects.filter(date=date)
            present_qs = Present.objects.filter(date=date)
            if (len(time_qs) > 0 or len(present_qs) > 0):
                qs = hours_vs_employee_given_date(present_qs, time_qs)

                return render(request, 'recognition/view_attendance_date.html', {'form': form, 'qs': qs})
            else:
                messages.warning(request, f'No records for selected date.')
                return redirect('view-attendance-date')








    else:

        form = DateForm()
        return render(request, 'recognition/view_attendance_date.html', {'form': form, 'qs': qs})


@login_required
def view_attendance_employee(request):
    if request.user.username != 'admin':
        return redirect('not-authorised')
    time_qs = None
    present_qs = None
    qs = None

    if request.method == 'POST':
        form = UsernameAndDateForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            if username_present(username):

                u = User.objects.get(username=username)

                time_qs = Time.objects.filter(user=u)
                present_qs = Present.objects.filter(user=u)
                date_from = form.cleaned_data.get('date_from')
                date_to = form.cleaned_data.get('date_to')

                if date_to < date_from:
                    messages.warning(request, f'Invalid date selection.')
                    return redirect('view-attendance-employee')
                else:

                    time_qs = time_qs.filter(date__gte=date_from).filter(date__lte=date_to).order_by('-date')
                    present_qs = present_qs.filter(date__gte=date_from).filter(date__lte=date_to).order_by('-date')

                    if (len(time_qs) > 0 or len(present_qs) > 0):
                        qs = hours_vs_date_given_employee(present_qs, time_qs, admin=True)
                        return render(request, 'recognition/view_attendance_employee.html', {'form': form, 'qs': qs})
                    else:
                        # print("inside qs is None")
                        messages.warning(request, f'No records for selected duration.')
                        return redirect('view-attendance-employee')






            else:
                print("invalid username")
                messages.warning(request, f'No such username found.')
                return redirect('view-attendance-employee')


    else:

        form = UsernameAndDateForm()
        return render(request, 'recognition/view_attendance_employee.html', {'form': form, 'qs': qs})


@login_required
def view_my_attendance_employee_login(request):
    if request.user.username == 'admin':
        return redirect('not-authorised')
    qs = None
    time_qs = None
    present_qs = None
    if request.method == 'POST':
        form = DateForm_2(request.POST)
        if form.is_valid():
            u = request.user
            time_qs = Time.objects.filter(user=u)
            present_qs = Present.objects.filter(user=u)
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            if date_to < date_from:
                messages.warning(request, f'Invalid date selection.')
                return redirect('view-my-attendance-employee-login')
            else:

                time_qs = time_qs.filter(date__gte=date_from).filter(date__lte=date_to).order_by('-date')
                present_qs = present_qs.filter(date__gte=date_from).filter(date__lte=date_to).order_by('-date')

                if (len(time_qs) > 0 or len(present_qs) > 0):
                    qs = hours_vs_date_given_employee(present_qs, time_qs, admin=False)
                    return render(request, 'recognition/view_my_attendance_employee_login.html',
                                  {'form': form, 'qs': qs})
                else:

                    messages.warning(request, f'No records for selected duration.')
                    return redirect('view-my-attendance-employee-login')
    else:

        form = DateForm_2()
        return render(request, 'recognition/view_my_attendance_employee_login.html', {'form': form, 'qs': qs})


@login_required
def logout(request):
    return redirect('home')
