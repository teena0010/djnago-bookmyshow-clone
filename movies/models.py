from django.db import models
from django.contrib.auth.models import User 
import re


class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True) 

    def __str__(self):
        return self.name

class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Movie(models.Model):
    name= models.CharField(max_length=255)
    image= models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3,decimal_places=1)
    cast= models.TextField()
    description= models.TextField(blank=True,null=True) # optional
    genres = models.ManyToManyField(Genre, related_name='movies')
    languages = models.ManyToManyField(Language, related_name='movies')
    release_date = models.DateField(db_index=True)

    def __str__(self):
        return self.name
    
    trailer_url = models.URLField(max_length=200, blank=True, null=True)

    @property
    def youtube_id(self):
        """
        Safely extracts the 11-character YouTube video ID from various URL formats.
        Prevents XSS by isolating the ID from potential malicious parameters.
        """
        if not self.trailer_url:
            return None
            
        # This regex catches standard (youtube.com/watch?v=) and short (youtu.be/) URLs
        match = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11}).*', self.trailer_url)
        return match.group(1) if match else None

class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(Movie,on_delete=models.CASCADE,related_name='theaters')
    time= models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

class Seat(models.Model):
    theater = models.ForeignKey(Theater,on_delete=models.CASCADE,related_name='seats')
    seat_number = models.CharField(max_length=10)
    is_booked=models.BooleanField(default=False)

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'

class Booking(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    seat=models.OneToOneField(Seat,on_delete=models.CASCADE)
    movie=models.ForeignKey(Movie,on_delete=models.CASCADE)
    theater=models.ForeignKey(Theater,on_delete=models.CASCADE)
    booked_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'Booking by{self.user.username} for {self.seat.seat_number} at {self.theater.name}'
    
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey('Movie', on_delete=models.CASCADE)
    seat_numbers = models.CharField(max_length=255) # e.g., "A1, A2"
    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    theater = models.ForeignKey('Theater', on_delete=models.CASCADE)
    
    # Tracking the Payment Gateway Status
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(max_length=50, default='Pending') # Pending, Paid, Failed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.user.username} - {self.payment_status}"

class ProcessedWebhook(models.Model):
    """
    SECURITY: This table prevents Replay Attacks. 
    If a hacker intercepts a successful webhook and sends it twice, 
    the unique constraint on event_id will block the duplicate.
    """
    event_id = models.CharField(max_length=255, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_id