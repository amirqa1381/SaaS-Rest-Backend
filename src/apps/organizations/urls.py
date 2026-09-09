from django.urls import path

from apps.organizations import views

app_name = "organizations"

urlpatterns = [
    path(
        "",
        views.OrganizationListCreateView.as_view(),
        name="organization-list",
    ),
    path(
        "<uuid:pk>/",
        views.OrganizationDetailView.as_view(),
        name="organization-detail",
    ),
    path(
        "<uuid:organization_pk>/settings/",
        views.OrganizationSettingsView.as_view(),
        name="organization-settings",
    ),
    path(
        "<uuid:organization_pk>/members/",
        views.MembershipListView.as_view(),
        name="membership-list",
    ),
    path(
        "<uuid:organization_pk>/members/<uuid:pk>/",
        views.MembershipDetailView.as_view(),
        name="membership-detail",
    ),
]