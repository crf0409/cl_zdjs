"""用户管理模块 - 视图函数"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden

from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
from .models import UserActivity

User = get_user_model()


def _get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _log_activity(user, action, detail='', request=None):
    """记录用户活动"""
    ip_address = _get_client_ip(request) if request else None
    UserActivity.objects.create(
        user=user,
        action=action,
        detail=detail,
        ip_address=ip_address,
    )


def register_view(request):
    """用户注册视图
    GET: 显示注册表单
    POST: 处理注册请求，创建新用户
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'注册成功！欢迎 {user.username}，请登录。')
            return redirect('login')
        else:
            messages.error(request, '注册失败，请检查输入信息。')
    else:
        form = UserRegistrationForm()

    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    """用户登录视图
    GET: 显示登录表单
    POST: 验证用户凭据并登录，记录登录活动
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    # 记录登录活动
                    _log_activity(user, 'login', '用户登录系统', request)
                    messages.success(request, f'欢迎回来，{user.username}！')
                    # 如果有next参数，跳转到目标页面
                    next_url = request.GET.get('next', 'dashboard')
                    return redirect(next_url)
                else:
                    messages.error(request, '该账号已被禁用，请联系管理员。')
            else:
                messages.error(request, '用户名或密码错误，请重试。')
    else:
        form = UserLoginForm()

    return render(request, 'users/login.html', {'form': form})


@login_required
def logout_view(request):
    """用户登出视图
    记录登出活动后注销用户
    """
    # 记录登出活动
    _log_activity(request.user, 'logout', '用户登出系统', request)
    logout(request)
    messages.info(request, '您已成功退出登录。')
    return redirect('login')


@login_required
def profile_view(request):
    """用户资料视图
    GET: 显示当前用户资料
    POST: 更新用户资料信息
    """
    user = request.user
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, '个人资料已更新。')
            return redirect('profile')
        else:
            messages.error(request, '更新失败，请检查输入信息。')
    else:
        form = UserProfileForm(instance=user)

    # 获取最近活动记录
    recent_activities = UserActivity.objects.filter(user=user)[:10]

    context = {
        'form': form,
        'recent_activities': recent_activities,
    }
    return render(request, 'users/profile.html', context)


@login_required
def user_list_view(request):
    """用户管理列表视图（仅管理员可访问）
    展示所有用户列表，支持分页和搜索
    """
    # 权限检查：仅管理员可访问
    if not request.user.is_admin:
        messages.error(request, '您没有权限访问此页面。')
        return HttpResponseForbidden('权限不足')

    # 搜索过滤
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')

    users = User.objects.all()
    if search_query:
        users = users.filter(username__icontains=search_query)
    if role_filter:
        users = users.filter(role=role_filter)

    # 分页
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'role_choices': User.ROLE_CHOICES,
    }
    return render(request, 'users/user_list.html', context)


@login_required
def activity_log_view(request):
    """活动日志视图
    管理员可查看所有用户活动，普通用户只能查看自己的活动
    """
    # 管理员可查看所有活动日志
    if request.user.is_admin:
        activities = UserActivity.objects.all()
    else:
        activities = UserActivity.objects.filter(user=request.user)

    # 按操作类型过滤
    action_filter = request.GET.get('action', '')
    if action_filter:
        activities = activities.filter(action=action_filter)

    # 按用户名搜索（仅管理员）
    username_filter = request.GET.get('username', '')
    if username_filter and request.user.is_admin:
        activities = activities.filter(user__username__icontains=username_filter)

    # 分页
    paginator = Paginator(activities, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'username_filter': username_filter,
        'action_choices': UserActivity.ACTION_CHOICES,
    }
    return render(request, 'users/activity_log.html', context)
