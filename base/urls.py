from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.loginPage, name="login"),
    path('logout/', views.logoutUser, name="logout"),
    path('register/', views.registerPage, name="register"),

    path('', views.home, name="home"),
    path('room/<str:pk>/', views.room, name="room"),
    path('profile/<str:pk>/', views.userProfile, name="user-profile"),

    path('create-room/', views.createRoom, name="create-room"),
    path('update-room/<str:pk>/', views.updateRoom, name="update-room"),
    path('delete-room/<str:pk>/', views.deleteRoom, name="delete-room"),
    path('delete-message/<str:pk>/', views.deleteMessage, name="delete-message"),

    path('update-user/', views.updateUser, name="update-user"),

    path('topics/', views.topicsPage, name="topics"),
    path('activity/', views.activityPage, name="activity"),

    path('follow-user/<str:pk>/', views.followUser, name="follow-user"),
    path('vote-room/<str:pk>/<str:vote_type>/', views.voteRoom, name="vote-room"),
    path('vote-message/<str:pk>/<str:vote_type>/', views.voteMessage, name="vote-message"),
    path('send-invitation/<str:room_pk>/<str:user_pk>/', views.sendInvitation, name="send-invitation"),
    path('respond-invitation/<str:pk>/<str:action>/', views.respondInvitation, name="respond-invitation"),
    path('invitations/', views.invitationsPage, name="invitations"),
]
