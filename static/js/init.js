$(function(){
    $('.table-list').dataTable();
    $('.sensor-list').dataTable({
        "aaSorting": [ [0, 'asc'], [1, 'asc'] ]
    });
});
