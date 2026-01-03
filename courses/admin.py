from django.contrib import admin
from .models import Course, Module


# Register your models here.

class ModuleInLine(admin.TabularInline):
    model = Module
    extra = 0

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    inlines = [ModuleInLine]

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "course")
    prepopulated_fields = {"slug": ("title",)}


    