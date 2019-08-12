# BSRC Internship Timeline/Notes
~~~~
               __  __                _  __    _  _____
              |  \/  | ___  ___ _ __| |/ /   / \|_   _|
              | |\/| |/ _ \/ _ \ '__| ' /   / _ \ | |
              | |  | |  __/  __/ |  | . \  / ___ \| |
              |_|  |_|\___|\___|_|  |_|\_\/_/   \_\_|

 _____                    _     ____       _           _
|_   _|_ _ _ __ __ _  ___| |_  / ___|  ___| | ___  ___| |_ ___  _ __
  | |/ _` | '__/ _` |/ _ \ __| \___ \ / _ \ |/ _ \/ __| __/ _ \| '__|
  | | (_| | | | (_| |  __/ |_   ___) |  __/ |  __/ (__| || (_) | |
  |_|\__,_|_|  \__, |\___|\__| |____/ \___|_|\___|\___|\__\___/|_|
                |___/
~~~~

## General Timeline:

- Week 1-2
  - Write code to query the Breakthrough Listen 1 million target database and
    test the returned results
  - Read reference papers to better understand the project
  - Read over code written by past interns to see what progress has already been
    made

- Week 3-5
  - Connect target selection to redis channel to select targets for observation
    as blocks come in
  - Publish target list to processing redis channel
  - Test code on simulation of the MeerKAT system

- Week 5-9
  - Pursue other avenues of improvement
    - Consider observational strategy and how to automate that. What should be
      done about potential repeat observations? If there are more targets than
      beams that can be formed, how might we go about choosing which targets
      should be observed? Given the amount of time an observation lasts, should
      we beam form on new targets given that the current observation is
      successful. How do we deal with with observing sources when potential sources
      of radio frequency interference, such as satellites, cross within the field
      of view?
    - Develop code that solves for the delay needed to beamform on the targets
      selected by the target selector
    - Quantify important figures of merit of this MeerKAT Commensal Survey to
      compare it to past SETI searches
    - Develop metrics for comparing the actual progress of the survey against
      its expected progress.

- Week 10
  - Finish poster and paper
  - Present poster


## Week 1:

### Progress:
 - Spent most of the week working on introduction work and
 - Wrote a basic version of a target selection function that takes telescope
   pointing coordinates and a beam radius and selects sources within the Open
   Exoplanet Catalogue that are within the beam radius

### Next Steps:
 - Approximated the distance of a target from some point as you would in cartesian
   coordinates. I need to modify this to work in spherical coordinates. Look into
   the [great-circle distance](https://en.wikipedia.org/wiki/Great-circle_distance)
 - Connect to the million target list database using MySQLdb and Pandas

## Week 2:

### Progress:
 - Modified my script to use the great-circle distance to calculate the angular
   distance between two points in the sky
 - Learned about Redis servers and how they're used within the MeerKAT Breakthrough
   Listen Backend
 - Subscribed to a sample Redis channel and published simple messages which were
   received and printed in a Jupyter notebook

### Next Steps:
 - Use the sample schedule block, [alerts.json](https://github.com/stevecroft/bl-interns/blob/master/tylerc/alerts.json), to process a message from the `schedule_block` Redis
   channel and find sources within the field of view of those pointings.

## Week 3:

### Progress:
 - Sent example schedule block message over the `schedule_block` channel. Was able
   to process those pointings and return sources within the field of view
 - Stored information about those sources, such as observation time, observation
   duration, and source id number, within that field of view in a MySQL database
   on my local machine
 - Published those sources to the `processing` channel
  - Wrote a listener to subscribe to the `processing` channel and publish a success/failure
    message to the `observation_status` channel
  - Subscribed to the `observation_status` channel and updated the MySQL database
    on my local machine with that success/failure message

### Next Steps:

 - Change channel names to include `product_id`
 - Look into timing of the code. When should messages be published to certain channels?
 - I'm sure I'm not publishing information that might be important to these observations.
   Look into what information needs to be publish along with the observation time,
   target ra/dec, etc.

## Week 4:
### Progress
 - Wrote a function to solve for the delays/weights needed to beamform on each
   target
    - Tested that function by simulating a mock array and passing in Information
      about the pointing coordinates of the array and the coordinates of the
      sources.
    - Will send plots/videos/data to Dave to look into how often the delay calculation
      needs to be updated over the course of the observation
 - Changed the structure of a few elements of code to listen to the `sensor_alerts`
   channel for schedule_block messages instead of the `schedule_block` channel

### Next Steps:
 - Look into pointing error requirements for this survey. This value should determine how
   often we will need to update the delay calculation. I'll need to look into if
   this needs to be made flexible depending on position.

## Week 5:

### Progress
 - Created plots the showed the delay difference over the course of a standard 5 minute observation.
 - Added error handling to the target selector

### Next Steps:

- Include more documentation and speed up the 

## Week 6:

### Progress
 - Created plots the showed the delay difference over the course of a standard 5 minute observation.
 -
### Next Steps:


### References:

#### Papers:

 1. [The Breakthrough Listen search for intelligent life: Target selection of nearby stars and galaxies.](https://arxiv.org/pdf/1701.06227.pdf)

 2. [The Breakthrough Listen search for intelligent life: 1.1–1.9 GHz observations of 692 nearby stars.](https://arxiv.org/pdf/1709.03491.pdf)

 3. [SETI and the Square Kilometre Array](https://arxiv.org/abs/1412.4867)

 4. [The Breakthrough Listen Search for Intelligent Life:
Observations of 1327 Nearby Stars over 1.10–3.45 GHz](https://arxiv.org/pdf/1906.07750.pdf)


#### Code/Software:

 - https://github.com/danielczech/meerkat-backend-interface.git

 - https://github.com/stevecroft/bl-interns/tree/master/loganp
