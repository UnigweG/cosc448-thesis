<?php

namespace Database\Seeders;

use App\Models\Roles;
use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

class UserSeeder extends Seeder
{
    /**
     * Seed the application's database.
     *
     * @return void
     */
    public function run()
    {
        // Empty Tables before Seeding
        DB::table('roles')->truncate();
        DB::table('users')->truncate();
        // creates none role
        $role = new Roles;
        $role->role = 'None';
        $role->num_monthly_bookings = 0;
        $role->max_booking_window = 0;
        $role->max_booking_duration = 0;
        $role->save();
        // create Staff role
        $role = new Roles;
        $role->role = 'Staff';
        $role->num_monthly_bookings = 8;
        $role->max_booking_window = 10;
        $role->max_booking_duration = 2;
        $role->save();

        // create Faculty role
        $role = new Roles;
        $role->role = 'Faculty';
        $role->num_monthly_bookings = 12;
        $role->max_booking_window = 21;
        $role->max_booking_duration = 8;
        $role->save();

        // create Graduate role
        $role = new Roles;
        $role->role = 'Graduate';
        $role->num_monthly_bookings = 12;
        $role->max_booking_window = 21;
        $role->max_booking_duration = 4;
        $role->save();

         // create Undergraduate role
        $role = new Roles;
        $role->role = 'Undergraduate';
        $role->num_monthly_bookings = 12;
        $role->max_booking_window = 21;
        $role->max_booking_duration = 4;
        $role->save();

        $role = new Roles;
        $role->role = 'Guest';
        $role->num_monthly_bookings = 10;
        $role->max_booking_window = 10;
        $role->max_booking_duration = 4;
        $role->save();

        // Admin Account - enter the info for you admin account
        $admin = User::create([
            'first_name' => 'Damyn',
            'last_name' => 'Admin',
            'bookings_used' => 0,
            'role_id' => $role->role_id,
            'email' => 'damyn@ubc.ca',
            'password' => Hash::make('password'), /*default local password is "password" */
            'is_admin' => TRUE,
        ]);

        // User Account - enter the info for you user account
        $user = User::create([
            'first_name' => 'Damyn',
            'last_name' => 'User',
            'bookings_used' => 0,
            'role_id' => $role->role_id,
            'email' => 'damyn@gmail.com',
            'password' => Hash::make('password'), /*default local password is "password" */
        ]);
    }
}
