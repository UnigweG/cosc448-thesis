<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     *
     * @return void
     */
    public function up()
    {
        Schema::create('rooms', function (Blueprint $table) {
            $table->id();
            $table->bigInteger('floor_id');
            $table->string('name', 30);
            $table->integer('occupancy');
            $table->integer('rows')->default(0);
            $table->integer('cols')->default(0);
            $table->boolean('is_closed')->default(FALSE);
            $table->foreign('floor_id')->references('id')->on('floors')->onDelete('cascade')->onUpdate('cascade');
            $table->timestamps();
            $table->softDeletes();
        });
    }

    /**
     * Reverse the migrations.
     *
     * @return void
     */
    public function down()
    {
        Schema::dropIfExists('rooms');
    }
};
