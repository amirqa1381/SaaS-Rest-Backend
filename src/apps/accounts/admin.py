from django.contrib import admin

# Register your models here.


class CustomAdminSite(admin.AdminSite):
    site_header = "SaaS Admin"
    site_title = "SaaS Admin Portal"
    index_title = "Welcome to the SaaS Admin Portal"

