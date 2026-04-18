"""用户管理模块 - 表单定义"""
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegistrationForm(forms.ModelForm):
    """用户注册表单"""
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入密码',
        }),
        min_length=6,
    )
    password_confirm = forms.CharField(
        label='确认密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请再次输入密码',
        }),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'department']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入用户名',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入邮箱',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入手机号',
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入部门',
            }),
        }

    def clean_password_confirm(self):
        """验证两次密码是否一致"""
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError('两次输入的密码不一致')
        return password_confirm

    def clean_username(self):
        """验证用户名是否已存在"""
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('该用户名已被注册')
        return username

    def save(self, commit=True):
        """保存用户，使用set_password加密密码"""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserLoginForm(forms.Form):
    """用户登录表单"""
    username = forms.CharField(
        label='用户名',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入用户名',
        }),
    )
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入密码',
        }),
    )


class UserProfileForm(forms.ModelForm):
    """用户资料编辑表单"""

    class Meta:
        model = User
        fields = ['email', 'phone', 'department', 'avatar']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'avatar': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
        }
