import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app, flash
from models import Course, Video, Pdf, User, Group, db
from sqlalchemy.exc import IntegrityError

class CourseService:
    
    @staticmethod
    def create_course(form_data, files):
        """Create a new course with content and assign to users/groups"""
        try:
            print("🚀 Starting course creation process...")
            
            # Extract form data
            title = form_data.get('title')
            description = form_data.get('description')
            category_id = form_data.get('category_id')
            assigned_user_ids = form_data.getlist('assigned_users')
            group_ids = form_data.getlist('group_ids')
            passing_score = int(form_data.get('passing_score', 70))
            test_required = 'test_required' in form_data
            
            print("1. Creating course object...")
            # Create course
            new_course = Course(
                title=title,
                description=description,
                category_id=category_id,
                passing_score=passing_score,
                test_required=test_required
            )
            db.session.add(new_course)
            db.session.commit()
            print(f"✅ Course created with ID: {new_course.id}")
            
            # Handle content uploads
            content_items = CourseService._process_content_uploads(new_course.id, form_data, files)
            if content_items:
                print(f"2. Adding {len(content_items)} content items...")
                db.session.add_all(content_items)
            
            # Handle test file if required
            if test_required:
                CourseService._process_test_file(new_course, form_data, files)
            
            # Assign course to users and groups
            CourseService._assign_course_to_users_and_groups(new_course, assigned_user_ids, group_ids)
            
            print("3. Final commit...")
            db.session.commit()
            print("🎉 Course creation completed!")
            
            return new_course, None
            
        except Exception as e:
            print(f"❌ Course creation error: {e}")
            db.session.rollback()
            return None, str(e)
    
    @staticmethod
    def _process_content_uploads(course_id, form_data, files):
        """Process and save content files (videos and PDFs)"""
        content_titles = form_data.getlist('content_titles[]')
        content_types = form_data.getlist('content_types[]')
        content_orders = form_data.getlist('content_orders[]')
        content_files = files.getlist('content_files[]')
        
        items_to_add = []
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        print(f"Processing {len(content_files)} files...")
        
        for i, file in enumerate(content_files):
            if file and file.filename:
                try:
                    content_type = content_types[i]
                    timestamp = int(datetime.utcnow().timestamp())
                    filename = f"{content_type}_{course_id}_{timestamp}_{secure_filename(file.filename)}"
                    file_path = os.path.join(upload_folder, filename)
                    
                    print(f"Saving file: {filename}")
                    file.save(file_path)
                    
                    if content_type == 'video':
                        item = Video(
                            title=content_titles[i],
                            video_path=filename,
                            course_id=course_id,
                            order=int(content_orders[i])
                        )
                    else:  # PDF
                        item = Pdf(
                            title=content_titles[i],
                            pdf_path=filename,
                            course_id=course_id,
                            order=int(content_orders[i])
                        )
                    
                    items_to_add.append(item)
                    print(f"Content item prepared: {filename}")
                    
                except Exception as e:
                    print(f"❌ Error processing file {file.filename}: {e}")
                    continue
        
        return items_to_add
    
    @staticmethod
    def _process_test_file(course, form_data, files):
        """Process and save test file"""
        test_file = files.get('test_file')
        pdf_question_count = form_data.get('pdf_question_count')
        pdf_answer_key = form_data.get('pdf_answer_key')
        
        if test_file and test_file.filename and pdf_question_count and pdf_answer_key:
            try:
                ext = os.path.splitext(test_file.filename)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                
                if ext == '.pdf':
                    filename = f"test_{course.id}_{timestamp}_{secure_filename(test_file.filename)}"
                    course.test_pdf = filename
                    course.test_images = None
                elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                    filename = f"testimg_{course.id}_{timestamp}_{secure_filename(test_file.filename)}"
                    course.test_images = filename
                    course.test_pdf = None
                else:
                    return
                
                test_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                test_file.save(test_file_path)
                
                course.test_question_count = int(pdf_question_count)
                course.test_answer_key = pdf_answer_key
                
                print(f"Test file saved: {filename}")
                
            except Exception as e:
                print(f"❌ Test file error: {e}")
                flash(f'Test dosyası kaydedilemedi: {str(e)}', 'warning')
    
    @staticmethod
    def _assign_course_to_users_and_groups(course, assigned_user_ids, group_ids):
        """Assign course to selected users and groups"""
        user_ids = set()
        
        # Add users from selected groups
        if group_ids:
            selected_groups = Group.query.filter(Group.id.in_(group_ids)).all()
            course.groups = selected_groups
            
            for group in selected_groups:
                for user in group.users:
                    user_ids.add(user.id)
            
            print(f"Added {len(user_ids)} users from {len(selected_groups)} groups")
        
        # Add individually selected users
        if assigned_user_ids:
            for user_id in assigned_user_ids:
                user_ids.add(int(user_id))
        
        # Assign all users to the course
        if user_ids:
            assigned_users = User.query.filter(User.id.in_(user_ids)).all()
            course.assigned_users = assigned_users
            print(f"Course assigned to {len(assigned_users)} users total") 