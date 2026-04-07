from django.db import models
import uuid


# Create your models here.
class Navigation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="navigations",
        null=True,
        blank=True,
    )
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_navigations",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return self.name

# Courses Model related to Navigation
class Courses(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    navigation = models.ForeignKey(
        Navigation,
        on_delete=models.CASCADE,
        related_name="courses",
    )
    slug = models.SlugField(max_length=150, unique=True)
    sort_order = models.IntegerField(default=0)
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    banner = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="courses",
        null=True,
        blank=True,
    )
    tags = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Comma-separated tags for this course",
    )
    is_popular = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_courses",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ['sort_order', 'created_at']
    def __str__(self):
        return self.name

# Homepage banner images
class HomepageBanner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    sort_order = models.IntegerField(default=0)
    have_link = models.BooleanField(default=False)
    link_url = models.URLField(blank=True, default="")
    button_link = models.CharField(max_length=100, blank=True, default="")
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="homepage_banners",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_homepage_banners",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ['sort_order', 'created_at']
    def __str__(self):
        return self.title

class Icons(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    sort_order = models.IntegerField(default=0)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="icons",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_icons",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return self.name

class PrincipalMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True, default="")
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="principal_messages",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_principal_messages",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.title

class Testimonial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, blank=True, default="")
    message = models.TextField(blank=True, default="")
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="testimonials",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_testimonials",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return f"{self.name} - {self.role}"

class Ads(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    link_url = models.URLField(blank=True, default="")
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="ads",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ads",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.title

class Careers(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    position = models.CharField(max_length=150, blank=True, default="")
    job_description = models.TextField(blank=True, default="")
    requirements = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="careers",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_careers",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return f"{self.title} - {self.position}"

class AboutUs(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="about_us_sections",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_about_us_sections",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.title

class Events(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    event_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_events",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.title

class Blogs(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    content = models.TextField(blank=True, default="")
    author = models.CharField(max_length=100, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_blogs",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.title

class FooterGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="footer_groups",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_footer_groups",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.name

class FooterLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    url = models.URLField(blank=True, default="")
    footer_group = models.ForeignKey(
        FooterGroup,
        on_delete=models.CASCADE,
        related_name="links",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_footer_links",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.name

class GalleryGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="gallery_groups",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_gallery_groups",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.name

class GalleryImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    caption = models.CharField(max_length=255, blank=True, default="")
    gallery_group = models.ForeignKey(
        GalleryGroup,
        on_delete=models.CASCADE,
        related_name="images",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_gallery_images",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    def __str__(self):
        return self.caption or f"Image {self.id}"

